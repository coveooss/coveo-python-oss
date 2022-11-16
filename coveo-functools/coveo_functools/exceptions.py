from typing import Any


class CoveoFunctoolsException(Exception):
    """Base class for coveo-functools exceptions."""


class Flexception(CoveoFunctoolsException):  # sorry for the pun :socanadian:
    """Base class for exceptions raised by the flex module."""


class UnsupportedAnnotation(Flexception, NotImplementedError):
    """When an annotation isn't supported."""


class PayloadMismatch(Flexception):
    """When the payload doesn't match the target type."""

    def __init__(self, value: Any, hint: Any, contains: Any) -> None:
        self.value = value
        self.hint = hint
        self.contains = contains

        super().__init__(
            f"I don't know how to fit {type(value)} "
            f"into {hint}{' of ' + str(contains) if contains else ''}"
        )
