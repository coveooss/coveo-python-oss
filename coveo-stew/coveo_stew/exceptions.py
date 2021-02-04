"""Exceptions thrown by the stew scripts."""


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
