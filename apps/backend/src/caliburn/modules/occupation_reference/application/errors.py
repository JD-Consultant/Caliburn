"""Reference failures are translated by transport adapters, never into empty hits."""


class ReferenceNotFoundError(LookupError):
    """The pinned reference or its task does not exist in this collection."""


class ReferenceIndexError(RuntimeError):
    """The index is unfinished, incompatible, or has inconsistent source identity."""


class ReferenceProviderError(RuntimeError):
    """A model or store returned an invalid result."""


class ReferenceQueryError(ValueError):
    """The query cannot be evaluated without losing its content."""


class ReferenceUnavailableError(RuntimeError):
    """Required local resources are not configured, loaded, or reachable."""


class RetrievalBusy(ReferenceUnavailableError):
    """The model lane did not become available before the admission deadline."""


class RetrievalUnavailable(ReferenceUnavailableError):
    """The application is shutting down and cannot admit retrieval work."""
