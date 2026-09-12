"""Configured host composition: reject stale client datasets before body/admission.

The public UUID is a scope check, not a secret or writer permission. Existing
Origin, command, reference, runtime and storage checks remain authoritative.
"""

from functools import partial
from uuid import UUID

from .catalog_api import CatalogBoundary, catalog_problem, create_catalog_app
from .generated.catalog_http import CatalogProblem, CatalogUuid


DATASET_HEADER = "X-JD-Dataset"
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class _DatasetGate:
    def __init__(self, app, *, dataset_id):
        self.app, self.dataset_id = app, dataset_id

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] in _UNSAFE_METHODS:
            values = [value for name, value in scope.get("headers", [])
                      if name.lower() == b"x-jd-dataset"]
            if len(values) != 1 or values[0].decode("latin-1") != self.dataset_id:
                return await catalog_problem(scope, "dataset_changed")(scope, receive, send)
        return await self.app(scope, receive, send)


class _ConfiguredBoundary(CatalogBoundary):
    def __init__(self, app, *, allowed_origins, dataset_id):
        # Existing safe boundary and Origin gate run before this inner dataset
        # check; the body limiter and all routes remain inside both gates.
        super().__init__(_DatasetGate(app, dataset_id=dataset_id), allowed_origins=allowed_origins)


def create_configured_api(resources, *, allowed_origins, dataset_id):
    try:
        if type(dataset_id) is not str or str(UUID(dataset_id)) != dataset_id:
            raise ValueError()
    except (TypeError, ValueError, AttributeError):
        raise ValueError("invalid_configured_dataset") from None
    app = create_catalog_app(resources, allowed_origins=allowed_origins,
        _boundary_factory=partial(_ConfiguredBoundary, dataset_id=dataset_id),
        _allowed_headers=("Content-Type", "If-Match", DATASET_HEADER))
    previous_openapi = app.openapi

    def configured_openapi():
        schema = previous_openapi()
        # Catalog routes already publish this generated model through FastAPI.
        # Keep its official schema and every route's existing conflict variants.
        schemas = schema.setdefault("components", {}).setdefault("schemas", {})
        schemas.setdefault("CatalogProblem", CatalogProblem.model_json_schema(
            mode="validation", ref_template="#/components/schemas/{model}"))
        problem_ref = {"$ref": "#/components/schemas/CatalogProblem"}
        for methods in schema["paths"].values():
            for method, operation in methods.items():
                if method.upper() not in _UNSAFE_METHODS:
                    continue
                parameters = operation.setdefault("parameters", [])
                if not any(value.get("in") == "header" and value.get("name") == DATASET_HEADER
                           for value in parameters):
                    parameters.append({"name": DATASET_HEADER, "in": "header", "required": True,
                        "description": "Expected dataset_id from the current document list; exactly one header is required.",
                        "schema": CatalogUuid.model_json_schema(mode="validation")})
                response = operation["responses"].setdefault("409", {"description": "Conflict"})
                content = response.setdefault("content", {}).setdefault("application/problem+json", {})
                existing = content.get("schema")
                if existing is None:
                    content["schema"] = problem_ref
                elif existing != problem_ref and problem_ref not in existing.get("anyOf", []):
                    content["schema"] = {"anyOf": [existing, problem_ref]}
        return schema

    app.openapi = configured_openapi
    return app
