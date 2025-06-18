import asyncio
import logging
from pathlib import Path
from subprocess import CalledProcessError
from typing import Any

import pytest

from coveo_systools.filesystem import find_application
from coveo_testing.logging import assert_logging
from coveo_testing.markers import UnitTest
from coveo_testing.parametrize import parametrize
from coveo_systools.subprocess import (
    DetailedCalledProcessError,
    log as called_process_error_logger,
    cast_command_line_argument_to_string,
    check_run,
    async_check_run,
    check_output,
    async_check_output,
)


def _forge_test_exception(
    original_exception: CalledProcessError, **kwargs: Any
) -> DetailedCalledProcessError:
    """forge a DetailedCalledProcessError exception using python's exception handlers."""
    try:
        raise DetailedCalledProcessError(**kwargs) from original_exception
    except DetailedCalledProcessError as forged_exception:
        return forged_exception


@UnitTest
@parametrize(
    "original_exception",
    (
        # command as str/list
        CalledProcessError(1, "command-str"),
        CalledProcessError(1, ("command", "list")),
        # bytes/str support in stdout/stderr
        CalledProcessError(1, "", b"stdout"),
        CalledProcessError(1, "", "stdout"),
        CalledProcessError(1, "", None, b"stderr"),
        CalledProcessError(1, "", None, "stderr"),
        # exit code support
        CalledProcessError(2, ""),
        CalledProcessError(0, ""),
        CalledProcessError(-1, ""),
    ),
)
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
            raise OSError("i am not really supported")
        except OSError:
            raise DetailedCalledProcessError
    except DetailedCalledProcessError as exception:
        assert isinstance(exception._wrapped_exception, OSError)
        assert "i am not really supported" in str(exception)


@UnitTest
def test_detailed_subprocess_exception_no_exception() -> None:
    """there's an error message when no exception is given as context."""
    with assert_logging(called_process_error_logger, absent="placebo"):
        # the logging only occurs when we use the exception
        exception = DetailedCalledProcessError()

    with assert_logging(called_process_error_logger, present="placebo", level=logging.ERROR):
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
@parametrize(
    ["argument", "expected"], (("string", "string"), (0, "0"), (0.0, "0.0"), (Path("."), "."))
)
def test_command_line_argument_conversion(argument: Any, expected: str) -> None:
    """tests the supported command line arg conversion types"""
    assert cast_command_line_argument_to_string(argument) == expected


@UnitTest
@parametrize("argument", (True, False, dict(), list(), tuple(), set(), object(), b""))
def test_command_line_argument_conversion_unsupported(argument: Any) -> None:
    """unsupported types will raise an exception to prevent mistakes"""
    with pytest.raises(ValueError):
        cast_command_line_argument_to_string(argument)


@UnitTest
@parametrize("command", (Path("git"), [Path("git")]))
def test_command_line_arguments_may_contain_non_strings(command: Any) -> None:
    """
    We pass in a non-string command then ensure that str() works.
    related to https://github.com/coveooss/coveo-python-oss/issues/132
    """
    exception = _forge_test_exception(CalledProcessError(1, cmd=command))
    assert "git" in str(exception)


@UnitTest
def test_detailed_process_error_cannot_render() -> None:
    """
    Ensure we never raise an exception in __str__
    related to https://github.com/coveooss/coveo-python-oss/issues/132
    """

    class Dummy:
        def __str__(self) -> str:
            raise TypeError("proof")

    exception = _forge_test_exception(CalledProcessError(1, cmd=Dummy()))  # type: ignore
    assert "proof" in str(exception)
    assert "error occurred when rendering" in str(exception)


async def _check_run(*command: Any) -> str:
    return await async_check_run(*command, capture_output=True)


def test_async_check_run() -> None:
    git = find_application("git", raise_if_not_found=True)
    assert asyncio.run(_check_run(git, "--version")).startswith("git version")


def test_async_check_run_exception() -> None:
    git = find_application("git", raise_if_not_found=True)
    try:
        asyncio.run(_check_run(git, "--crash"))
        assert False, "Did not raise"
    except DetailedCalledProcessError as exception:
        assert exception.returncode == 129
        assert "unknown option: --crash" in exception.decode_stderr()
        # test for fix https://github.com/coveooss/coveo-python-oss/issues/132
        # without the fix, str(exception) will raise an exception because the `git` variable was given as a Path
        assert str(exception)


def test_check_run_remove_ansi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that ANSI codes can be optionally preserved in the output."""
    ansi_text = "\033[31mred text\033[0m"

    def mock_run(*args: Any, **kwargs: Any) -> Any:
        class MockProcess:
            returncode = 0
            stdout = ansi_text.encode()
            stderr = b""

        return MockProcess()

    # Patch subprocess.run
    monkeypatch.setattr("subprocess.run", mock_run)

    # When remove_ansi is True (default), ANSI codes should be removed
    # with check_run
    result_filtered = check_run("dummy-command", capture_output=True)
    assert result_filtered == "red text"
    # with check_output
    result_filtered = check_output("dummy-command")
    assert result_filtered == "red text"

    # When remove_ansi is False, ANSI codes should be preserved
    # with check_run
    result_preserved = check_run("dummy-command", capture_output=True, remove_ansi=False)
    assert result_preserved == ansi_text
    # with check_output
    result_preserved = check_output("dummy-command", remove_ansi=False)
    assert result_preserved == ansi_text


async def _check_run_ansi(*command: Any, remove_ansi: bool = True) -> str:
    return await async_check_run(*command, capture_output=True, remove_ansi=remove_ansi)


async def _check_output_ansi(*command: Any, remove_ansi: bool = True) -> str:
    return await async_check_output(*command, remove_ansi=remove_ansi)


def test_async_check_output_remove_ansi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that ANSI codes can be optionally preserved in async output."""
    ansi_text = "\033[31mred text\033[0m"

    class MockProcess:
        async def communicate(self) -> tuple[bytes, bytes]:
            return ansi_text.encode(), b""

        @property
        def returncode(self) -> int:
            return 0

    async def mock_create_subprocess_exec(*args: Any, **kwargs: Any) -> MockProcess:
        return MockProcess()

    # Patch asyncio.create_subprocess_exec
    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_create_subprocess_exec)

    # When remove_ansi is True (default), ANSI codes should be removed
    # with check_run
    result_filtered = asyncio.run(_check_run_ansi("dummy-command"))
    assert result_filtered == "red text"
    # with check_output
    result_filtered = asyncio.run(_check_output_ansi("dummy-command"))
    assert result_filtered == "red text"

    # When remove_ansi is False, ANSI codes should be preserved
    # with check_run
    result_preserved = asyncio.run(_check_run_ansi("dummy-command", remove_ansi=False))
    assert result_preserved == ansi_text
    # with check_output
    result_preserved = asyncio.run(_check_output_ansi("dummy-command", remove_ansi=False))
    assert result_preserved == ansi_text
