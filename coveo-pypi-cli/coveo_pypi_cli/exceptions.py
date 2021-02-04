class PypiCliException(Exception):
    ...


class VersionException(PypiCliException):
    ...


class VersionExists(VersionException):
    ...
