"""Tests around the logging tools."""

from contextlib import contextmanager
import logging
from typing import Tuple, Iterable, Generator
from uuid import uuid4

import pytest

from coveo_testing.logging import intercept_logging, assert_logging
from coveo_testing.markers import UnitTest
from coveo_testing.parametrize import parametrize


log = logging.getLogger(__name__)
log.level = logging.INFO


def _get_test_strings(amount: int) -> Tuple[str, ...]:
    """returns a tuple of 'amount' unique strings"""
    strings = []
    while amount:
        strings.append(str(uuid4()))
        amount -= 1
    assert len(set(strings)) == len(strings)  # no duplicates
    return tuple(strings)


@contextmanager
def _to_raise_or_not_to_raise(*, raises: bool) -> Generator[None, None, None]:
    """shorthand to cut on repetitions / simplify code."""
    __tracebackhide__ = True
    if raises:
        with pytest.raises(AssertionError):
            yield
    else:
        yield


@UnitTest
def test_intercept_logging() -> None:
    """Test that the intercept_logging works correctly."""
    str1, str2 = _get_test_strings(2)

    log.info(str1)
    with intercept_logging(log) as stream:
        log.info(str2)
        logs = stream.getvalue()

    assert str2 in logs
    assert str1 not in logs


@UnitTest
def test_intercept_logging_includes_more_severe_levels() -> None:
    """The logging assert always includes logging levels that are more important than desired."""
    str1, str2, str3 = _get_test_strings(3)
    assert log.level != logging.DEBUG
    with intercept_logging(log, level=logging.DEBUG) as stream:
        assert log.level == logging.DEBUG
        log.error(str1)
        log.info(str2)
        log.debug(str3)
        logs = stream.getvalue()

    assert str1 in logs
    assert str2 in logs
    assert str3 in logs
    assert log.level != logging.DEBUG


@UnitTest
def test_intercept_logging_excludes_less_severe_levels() -> None:
    """The logging assert will exclude logging levels that are less important then desired."""
    str1, str2, str3 = _get_test_strings(3)
    assert log.level != logging.ERROR
    with intercept_logging(log, level=logging.ERROR) as stream:
        assert log.level == logging.ERROR
        log.error(str1)
        log.warning(str2)
        log.info(str3)
        logs = stream.getvalue()

    assert str1 in logs
    assert str2 not in logs
    assert str3 not in logs
    assert log.level != logging.ERROR


@UnitTest
@parametrize("presence", ("present", "absent"))
def test_assert_logging_present_absent(presence: str) -> None:
    """Test the assert_logging function success using simple strings."""
    to_assert = to_log = str(uuid4())

    if presence == "present":
        # add some garbage around the string, it will find it as a substring
        to_log = f"zz{to_log}zz"
    else:
        # remove one character from the string so that the match fails 1 character short
        to_log = to_log[:-1]

    with assert_logging(log, **{presence: to_assert}, level=logging.INFO):
        log.info(to_log)


@UnitTest
@parametrize("presence", ("present", "absent"))
def test_assert_logging_present_absent_failure(presence: str) -> None:
    """Test the assert_logging function failure using simple strings."""
    to_assert = to_log = str(uuid4())

    if presence == "absent":
        # add some garbage around the logged string, it will fail even as a substring
        to_log = f"zz{to_log}zz"
    else:
        # remove one character from the logged string so that it cannot find the full string
        to_log = to_log[:-1]

    with pytest.raises(AssertionError):
        with assert_logging(log, **{presence: to_assert}, level=logging.INFO):
            log.info(to_log)


@UnitTest
def test_assert_logging_from_now() -> None:
    """make sure the logger doesn't see past logs :shrug:"""
    past = str(uuid4())
    log.info(past)
    with assert_logging(log, absent=past):
        log.info("whatever")


@UnitTest
@parametrize(
    ["present", "absent"],
    (
        pytest.param(_get_test_strings(2), tuple(), id="present"),
        pytest.param(tuple(), _get_test_strings(2), id="absent"),
        pytest.param(_get_test_strings(2), _get_test_strings(2), id="present+absent"),
    ),
)
@parametrize("test_function_name", ("success", "fail_present", "fail_absent"))
def test_assert_logging_multiple_present_absent(
    present: Tuple[str, ...], absent: Tuple[str, ...], test_function_name: str
) -> None:
    """test mixing absent and present together in success+failure scenarios."""

    def success() -> Iterable[str]:
        yield from present

    def fail_present() -> Iterable[str]:
        if not present:
            pytest.skip("invalid test case")
        # omit one of the "present" item to make it fail
        assert len(present) >= 2
        yield from present[1:]

    def fail_absent() -> Iterable[str]:
        if not absent:
            pytest.skip("invalid test case")
        # include one of the "absent" item to make it fail
        yield from present
        yield absent[0]

    log_generator_function = locals()[test_function_name]
    with _to_raise_or_not_to_raise(raises=test_function_name.startswith("fail")):
        with assert_logging(log, present=present, absent=absent):
            for line in log_generator_function():
                log.info(line)
