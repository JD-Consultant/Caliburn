"""Reference failures are translated by transport adapters, never into empty hits."""


class ReferenceNotFoundError(LookupError):
    """The pinned reference or its task does not exist in this collection."""


class ReferenceIndexError(RuntimeError):
    """The index is unfinished, incompatible, or has inconsistent source identity."""


class ReferenceProviderError(RuntimeError):
    """A model or store returned an invalid result."""


class ReferenceQueryError(ValueError):
    """The query cannot be evaluated without losing its content."""
