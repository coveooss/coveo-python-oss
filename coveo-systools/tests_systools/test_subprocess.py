import logging
from pathlib import Path
from subprocess import CalledProcessError
from typing import Any

import pytest
from coveo_testing.logging import assert_logging
from coveo_testing.markers import UnitTest
from coveo_testing.parametrize import parametrize
from coveo_systools.subprocess import DetailedCalledProcessError, log as called_process_error_logger, \
    cast_command_line_argument_to_string


def _forge_test_exception(original_exception: CalledProcessError, **kwargs) -> DetailedCalledProcessError:
    """forge a DetailedCalledProcessError exception using python's exception handlers."""
    try:
        raise DetailedCalledProcessError(**kwargs) from original_exception
    except DetailedCalledProcessError as forged_exception:
        return forged_exception


@UnitTest
@parametrize('original_exception', (
    # command as str/list
    CalledProcessError(1, 'command-str'),
    CalledProcessError(1, ('command', 'list')),

    # bytes/str support in stdout/stderr
    CalledProcessError(1, '', b'stdout'),
    CalledProcessError(1, '', 'stdout'),
    CalledProcessError(1, '', None, b'stderr'),
    CalledProcessError(1, '', None, 'stderr'),

    # exit code support
    CalledProcessError(2, ''),
    CalledProcessError(0, ''),
    CalledProcessError(-1, '')
))
def test_detailed_subprocess_exception_attributes(original_exception: CalledProcessError) -> None:
    """Tests that the attributes fallback to the underlying exception."""
    exception = _forge_test_exception(original_exception)

    # maps to the original error
    assert exception.returncode == original_exception.returncode
    assert exception.cmd == original_exception.cmd
    assert exception.output == original_exception.stdout
    assert exception.stderr == original_exception.stderr

    # some attributes have automatic conversions
    assert isinstance(exception.command_str(), str)
    assert original_exception.stdout is None or isinstance(exception.decode_stdout(), str)
    assert original_exception.stderr is None or isinstance(exception.decode_stderr(), str)


@UnitTest
def test_detailed_subprocess_exception_wrong_exception() -> None:
    """there's an error message when the wrong exception is given in the magic-handler form, but
    we try to retain it as much as we can."""
    try:
        try:
            raise OSError('i am not really supported')
        except OSError:
            raise DetailedCalledProcessError
    except DetailedCalledProcessError as exception:
        assert isinstance(exception._wrapped_exception, OSError)
        assert 'i am not really supported' in str(exception)


@UnitTest
def test_detailed_subprocess_exception_no_exception() -> None:
    """there's an error message when no exception is given as context."""
    with assert_logging(called_process_error_logger, absent='placebo'):
        # the logging only occurs when we use the exception
        exception = DetailedCalledProcessError()

    with assert_logging(called_process_error_logger, present='placebo', level=logging.ERROR):
        str(exception)


@UnitTest
def test_detailed_subprocess_exception_precedence() -> None:
    """make sure `raise from` takes precedence over the context."""
    ex1 = Exception()
    ex2 = Exception()
    try:
        try:
            raise ex1
        except Exception as caught_ex1:
            assert caught_ex1 is ex1
            raise DetailedCalledProcessError from ex2
    except DetailedCalledProcessError as exception:
        assert exception._wrapped_exception is ex2


@UnitTest
@parametrize(['argument', 'expected'], (
    ('string', 'string'),
    (0, '0'),
    (0.0, '0.0'),
    (Path('.'), '.')
))
def test_command_line_argument_conversion(argument: Any, expected: str) -> None:
    """tests the supported command line arg conversion types"""
    assert cast_command_line_argument_to_string(argument) == expected


@UnitTest
@parametrize('argument', (True, False, dict(), list(), tuple(), set(), object(), b''))
def test_command_line_argument_conversion_unsupported(argument: Any) -> None:
    """unsupported types will raise an exception to prevent mistakes"""
    with pytest.raises(ValueError):
        cast_command_line_argument_to_string(argument)
