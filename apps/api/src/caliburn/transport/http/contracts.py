"""FastAPI retains its generated DTO/OpenAPI while canonical schemas admit request bodies."""

from functools import partial

from pydantic import BaseModel, BeforeValidator

from caliburn.contracts.validation import validate_contract


def canonical_body(model: type[BaseModel]) -> BeforeValidator:
    return BeforeValidator(partial(validate_contract, model))
