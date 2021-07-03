class CoveoFunctoolsException(Exception):
    """Base class for coveo-functools exceptions."""


class FlexException(CoveoFunctoolsException):
    """Base class for exceptions raised by the flex module."""


class AmbiguousAnnotation(FlexException):
    """An invalid union was provided."""
