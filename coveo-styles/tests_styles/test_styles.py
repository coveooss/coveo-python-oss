from unittest.mock import PropertyMock

import sys
from unittest import mock

from coveo_testing.markers import UnitTest

from coveo_styles.styles import ExitWithFailure, _pretty_excepthook, Pretty, echo


@UnitTest
def test_exit_with_failure_exit_code_attribute() -> None:
    assert ExitWithFailure().exit_code == 1
    assert ExitWithFailure(exit_code=3).exit_code == 3


@UnitTest
def test_exit_with_failure_exit_code() -> None:
    try:
        raise ExitWithFailure(exit_code=5) from ValueError('whatever')
    except ExitWithFailure:
        try:
            _pretty_excepthook(*sys.exc_info())
        except SystemExit as exception:
            assert exception.code == 5
            return  # TEST PASS

    assert False


@UnitTest
def test_disable_emoji() -> None:
    assert echo.passthrough.prettify('!!robot_face!!') == '\U0001F916\x1b[0m'
    try:
        Pretty.set_safe_encode()
        with mock.patch('sys.stdout') as stdout_mock:
            stdout_mock.encoding = 'cp1258'
            assert echo.passthrough.prettify('!!robot_face!!') == '\x1b[0m'
    finally:
        Pretty.set_safe_encode(False)
    assert echo.passthrough.prettify('!!robot_face!!') == '\U0001F916\x1b[0m'
