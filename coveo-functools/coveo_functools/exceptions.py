class CoveoFunctoolsException(Exception):
    """Base class for coveo-functools exceptions."""


class Flexception(CoveoFunctoolsException):  # sorry for the pun :socanadian:
    """Base class for exceptions raised by the flex module."""


class UnsupportedAnnotation(Flexception, NotImplementedError):
    """When an annotation isn't suported."""
