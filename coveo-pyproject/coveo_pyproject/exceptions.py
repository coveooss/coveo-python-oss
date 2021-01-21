"""Exceptions thrown by the pyproject scripts."""


class PythonProjectException(Exception):
    ...


class CannotLoadProject(PythonProjectException):
    ...


class RequirementsOutdated(PythonProjectException):
    ...


class PythonProjectNotFound(PythonProjectException):
    ...


class MypyNotFound(PythonProjectException):
    ...


class CheckFailed(PythonProjectException):
    ...
