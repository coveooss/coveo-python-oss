class RefException(Exception):
    """Base class for ref exceptions."""


class UsageError(RefException):
    """When ref detects usage errors."""


class NoQualifiedName(RefException, NotImplementedError):
    """When something has apparently no qualified name."""


class CannotImportModule(RefException, ImportError):
    """Occurs when an import fails."""


class CannotFindSymbol(RefException, AttributeError):
    """Occurs when a symbol cannot be imported from a module."""


class DuplicateSymbol(CannotFindSymbol):
    """Occurs when a symbol occurs more than once within a module."""
