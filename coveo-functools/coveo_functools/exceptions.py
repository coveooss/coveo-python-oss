class CoveoFunctoolsException(Exception):
    """Base class for coveo-functools exceptions."""


class FlexException(CoveoFunctoolsException):
    """Base class for exceptions raised by the flex module."""


class UnsupportedAnnotation(FlexException, NotImplementedError):
    """When an annotation isn't suported."""
