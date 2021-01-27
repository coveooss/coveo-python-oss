""" Various testing tools involving loggers. """

from contextlib import contextmanager
import logging
from io import StringIO
from types import TracebackType
from typing import Generator, Iterable, Optional


StringCollection = Iterable[str]


class SetLoggingLevel:
    """
    Class used to change the logging level for a block of code.

    For example, we can change the logging level for 'elasticsearch' to ERROR while calling DoSomething:

            with SetLoggingLevel('elasticsearch', logging.ERROR):
                DoSomething()

    """

    def __init__(self, logger_name: str, logging_level: int = logging.CRITICAL) -> None:
        """
        Initializer.

        :param logger_name: The logger name.
        :param logging_level: The temporary logging level.
        """
        self._logger = logging.getLogger(logger_name)  # Create logger if it does not exists yet.
        assert self._logger
        self._logging_level = logging_level
        self._old_logging_level: Optional[int] = None

    def __enter__(self) -> None:
        """
        Change the logging level.
        """
        self._old_logging_level = self._logger.getEffectiveLevel()
        self._logger.setLevel(self._logging_level)

    # noinspection PyUnusedLocal
    def __exit__(
        self,
        _exc_type: Optional[type],
        _exc_val: Optional[Exception],
        _exc_tb: Optional[TracebackType],
    ) -> None:
        """
        Restore the logging level to its original value.
        """
        self._logger.setLevel(self._old_logging_level)
        assert self._logger.getEffectiveLevel() == self._old_logging_level


@contextmanager
def intercept_logging(logger: logging.Logger, level: int = None) -> Generator[StringIO, None, None]:
    """
    Context manager. Add a temporary stream handler to a logger.

    :param logger: a python logger
    :param level: a python log level
    :return: yields the stream (use .get_value() to extract the stuff!)
    """
    __tracebackhide__ = True
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)

    with SetLoggingLevel(logger.name, level or logger.level):
        yield stream
        handler.flush()

    logger.removeHandler(handler)


@contextmanager
def assert_logging(
    logger: logging.Logger,
    present: StringCollection = None,
    absent: StringCollection = None,
    level: int = None,
) -> Generator[None, None, None]:
    """
    Context manager that attaches to a logger and ensures the presence of specific strings when the context is left.
    An assert will be raised as soon as a string from `intercepts` is missing from the logs.

    :param logger: a python logger
    :param present: An iterable of strings to find in the logs (case sensitive)
    :param absent: An iterable of strings that must NOT be found in the logs (case sensitive)
    :param level: specify a logging level for this handler only.
    """
    __tracebackhide__ = True
    if isinstance(present, str):
        present = (present,)

    if isinstance(absent, str):
        absent = (absent,)

    with intercept_logging(logger, level) as stream:
        try:
            yield
        finally:
            logs = stream.getvalue()
            if present:
                assert logs.strip(), "log output was silent"
                for line in present:
                    assert line in logs, f'String "{line}" cannot be found in the logs:\n{logs}'
            if absent:
                for line in absent:
                    assert line not in logs, f'String "{line}" was found in the logs:\n{logs}'
