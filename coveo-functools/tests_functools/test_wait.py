""" Tests the wait method features """

import datetime
from typing import List, Type, Tuple, TypedDict

from coveo_testing.markers import UnitTest
from coveo_testing.parametrize import parametrize
import pytest

from coveo_functools import wait
from coveo_functools.wait import TimeoutValue, Backoff, NoBackoff, MaxBackoffException


NOW = datetime.datetime.now


@UnitTest
def test_until() -> None:
    """Tests the basic behavior of wait.until"""
    # Test success
    val = True
    wait.until(lambda: val)
    assert val

    # Test failure
    val = False
    with pytest.raises(wait.TimeoutExpired):
        wait.until(lambda: val, timeout_s=datetime.timedelta(milliseconds=1))
    assert not val

    # check waiting behavior and timers
    val2 = NOW()
    val2 += datetime.timedelta(milliseconds=30)

    # value should be true very soon!
    wait.until(lambda: NOW() > val2, timeout_s=datetime.timedelta(milliseconds=31))
    assert NOW() > val2

    # this one shall fail
    val2 = NOW()
    val2 += datetime.timedelta(seconds=1)

    with pytest.raises(wait.TimeoutExpired):
        wait.until(lambda: NOW() > val2, timeout_s=datetime.timedelta(milliseconds=1))


@UnitTest
@parametrize("timeout,retry", [(25, 5), (5, 1), (10, 50), (25, 25)])
def test_until_timeout_retry(timeout: int, retry: int) -> None:
    """Tests various timeout and retry values"""
    timestamp = NOW()
    with pytest.raises(wait.TimeoutExpired):
        wait.until(
            lambda: False,
            timeout_s=datetime.timedelta(milliseconds=timeout),
            retry_ms=datetime.timedelta(milliseconds=retry),
        )
    assert NOW() - timestamp >= datetime.timedelta(milliseconds=timeout)


@UnitTest
def test_until_infinite_timeout() -> None:
    """Tests waiting for an infinite timeout."""
    timestamp = NOW()
    retry_ms = 1
    count = [0]
    max_count = 10

    def raise_if_called_more_than_max_count_times() -> None:
        """Raise an exception when we reach the maximum number of calls."""
        count[0] += 1
        if count[0] > max_count:
            raise InterruptedError

    with pytest.raises(InterruptedError):
        wait.until(
            raise_if_called_more_than_max_count_times,
            timeout_s=None,
            retry_ms=datetime.timedelta(milliseconds=retry_ms),
        )
    assert count[0] > max_count
    assert NOW() - timestamp >= datetime.timedelta(milliseconds=max_count * retry_ms)


@UnitTest
def test_until_wait() -> None:
    """Test waiting for a condition"""
    val = NOW() + datetime.timedelta(milliseconds=30)

    # value should be true very soon
    wait.until(lambda: NOW() > val, timeout_s=datetime.timedelta(milliseconds=31))
    assert NOW() > val


@UnitTest
def test_until_wait_timeout() -> None:
    """Test a condition that will never become true"""
    val = NOW() + datetime.timedelta(milliseconds=100)

    with pytest.raises(wait.TimeoutExpired):
        wait.until(lambda: NOW() > val, timeout_s=datetime.timedelta(milliseconds=10))


@UnitTest
@parametrize("timeout", [10, 20, 45])
def test_until_retry(timeout: int) -> None:
    """Assert retry length"""
    retries = []

    with pytest.raises(wait.TimeoutExpired):
        wait.until(lambda: retries.append(NOW()), timeout_s=0.05, retry_ms=timeout)

    first = retries.pop(0)
    for retry in retries:
        assert retry - first >= datetime.timedelta(milliseconds=timeout)


class TimeoutValues(TypedDict):
    timeout_s: TimeoutValue
    retry_ms: TimeoutValue


_timeout: TimeoutValues = {
    "timeout_s": datetime.timedelta(milliseconds=4),
    "retry_ms": datetime.timedelta(milliseconds=1),
}


def _raise(exception: Type[Exception]) -> None:
    """delegate for the tests below"""
    raise exception


@UnitTest
def test_until_suppress_all_exceptions() -> None:
    with pytest.raises(wait.TimeoutExpired):
        wait.until(lambda: _raise(Exception), handle_exceptions=True, **_timeout)


@UnitTest
def test_until_suppress_subclass() -> None:
    with pytest.raises(wait.TimeoutExpired):
        wait.until(lambda: _raise(TypeError), handle_exceptions=True, **_timeout)


@UnitTest
def test_until_raise_on_exception() -> None:
    with pytest.raises(NotImplementedError):
        wait.until(lambda: _raise(NotImplementedError))

    # same test with False instead of None, should yield same result
    with pytest.raises(NotImplementedError):
        wait.until(lambda: _raise(NotImplementedError), handle_exceptions=False)


@UnitTest
def test_until_suppress_exception_tuple() -> None:
    with pytest.raises(wait.TimeoutExpired):
        wait.until(
            lambda: _raise(NotImplementedError),
            handle_exceptions=(NotImplementedError,),
            **_timeout
        )


@UnitTest
def test_until_suppress_exception_tuple_conversion() -> None:
    # test conversion to tuple
    with pytest.raises(wait.TimeoutExpired):
        wait.until(
            lambda: _raise(NotImplementedError), handle_exceptions=NotImplementedError, **_timeout
        )


@UnitTest
def test_until_cannot_suppress_own_exception() -> None:
    # make sure we can't suppress its own exception
    with pytest.raises(wait.TimeoutExpired):
        wait.until(lambda: False, handle_exceptions=(wait.TimeoutExpired,), **_timeout)


@UnitTest
def test_until_custom_exception() -> None:
    class DummyException(Exception):
        """DummyException1"""

    class DummyException2(Exception):
        """DummyException2"""

    i = 0

    def _raise_both() -> None:
        nonlocal i
        if i:
            raise DummyException()
        i += 1
        raise DummyException2()

    # test tuple
    with pytest.raises(DummyException2):
        wait.until(_raise_both, handle_exceptions=(DummyException,), **_timeout)

    # test tuple again
    i = 0
    with pytest.raises(DummyException):
        wait.until(_raise_both, handle_exceptions=(DummyException2,), **_timeout)

    # ultimate test tuple :)
    i = 0
    with pytest.raises(wait.TimeoutExpired):
        wait.until(_raise_both, handle_exceptions=(DummyException2, DummyException), **_timeout)


def _verify_backoff_output(backoff: Backoff, expected_results: List[float]) -> None:
    """Checks that the output of a backoff matches a list, bypassing jitter."""
    assert sorted(backoff._stages) == sorted(
        set(expected_results)
    )  # expected results includes max retries
    assert tuple(sorted(backoff._stages)) == backoff._stages

    try:
        while True:
            try:
                wait_time = expected_results.pop(0)
                assert wait_time <= next(backoff) <= wait_time + 0.5
            except IndexError:
                try:
                    next(backoff)
                except MaxBackoffException:
                    break
                assert False, "Iteration of expected results stopped prematurely."

    except MaxBackoffException:
        assert False, "Iteration of backoff ended prematurely."


# noinspection PyArgumentEqualDefault
@parametrize(
    "backoff,expected_results",
    [
        (
            Backoff(first_wait=1, max_backoff=5, max_backoff_attempts=5, growth=2),
            [1, 2, 4, 5, 5, 5, 5, 5],
        ),
        (
            Backoff(first_wait=2, max_backoff=20, max_backoff_attempts=3, growth=2),
            [2, 4, 8, 16, 20, 20, 20],
        ),
        # floats
        (
            Backoff(first_wait=1, max_backoff=3, max_backoff_attempts=1, growth=1.5),
            [1, 1.5, 2.25, 3],
        ),
        # ensure growth with small floats
        (
            Backoff(first_wait=0.2, max_backoff=0.21, max_backoff_attempts=3, growth=1.1),
            [0.2, 0.21, 0.21, 0.21],
        ),
        # safeguard, first_wait will be 0.2, backoff 0.8, attempts 2, growth 2:
        (
            Backoff(first_wait=0, max_backoff=-0.8, max_backoff_attempts=-2, growth=1),
            [0.2, 0.4, 0.8, 0.8],
        ),
        # safeguard, first_wait and growth will be absolute
        (Backoff(first_wait=-1, max_backoff=4, max_backoff_attempts=1, growth=-2), [1, 2, 4]),
    ],
)
@UnitTest
def test_backoff(backoff: Backoff, expected_results: List[float]) -> None:
    """Tests valid backoff scenarios."""
    _verify_backoff_output(backoff, expected_results)


@parametrize(
    "backoff,expected_results",
    [
        # wrong wait time value
        (Backoff(), [0]),
        # not enough results to cover all results
        (Backoff(first_wait=1, max_backoff=8, growth=2), [1, 2, 4]),
        # not enough results to cover max_backoff_attempts
        (Backoff(first_wait=1, max_backoff=8, max_backoff_attempts=5, growth=2), [1, 2, 4, 8, 8]),
        # too many results
        (
            Backoff(first_wait=1, max_backoff=8, max_backoff_attempts=2, growth=2),
            [1, 2, 4, 8, 8, 8],
        ),
        # just plain wrong, unnecessary and evil
        (
            Backoff(first_wait=0, max_backoff=0, max_backoff_attempts=0, growth=0),
            [1, 2, 4, 8, 8, 8],
        ),
    ],
)
@UnitTest
def test_verify_backoff(backoff: Backoff, expected_results: List[float]) -> None:
    """Make sure the verify method actually throws/asserts on errors."""
    with pytest.raises(AssertionError):
        _verify_backoff_output(backoff, expected_results)


@UnitTest
def test_no_backoff() -> None:
    """Tests the NoBackoff class."""
    backoff = NoBackoff()

    with pytest.raises(MaxBackoffException):
        next(backoff)

    # reset has no effect
    backoff.reset()


@UnitTest
def test_verify_backoff_endless() -> None:
    """
    Verifies that Backoff supports endless iteration.
    """
    target_maximum = 10
    backoff = Backoff(
        first_wait=target_maximum, max_backoff=target_maximum, max_backoff_attempts=None, growth=10
    )

    for _ in range(1000):  # Ok ok not endless, but "endless"
        try:
            assert backoff.percent_to_max_time() == 1
            val = next(backoff)
        except MaxBackoffException:
            pytest.fail("Backoff raised RetriesExhausted while in endless mode.")
        else:
            assert target_maximum <= val <= target_maximum + 0.5


@UnitTest
def test_verify_backoff_render_on_endless() -> None:
    """Verifies that you can list() an infinite backoff."""
    backoff = Backoff(first_wait=1, max_backoff=8, max_backoff_attempts=None, growth=2)
    assert backoff._stages == (1, 2, 4, 8)


@parametrize("stages", ((1, 2, 4, 5), (2, 3, 4, 5), (2, 4.5, 9.25, 16.5)))
@UnitTest
def test_backoff_percent_to_max_time(stages: Tuple[float, ...]) -> None:
    backoff = Backoff(stages=stages)

    for loop in range(len(stages)):
        assert backoff.percent_to_max_time() == stages[loop] / stages[-1]
        assert stages[loop] <= next(backoff) <= stages[loop] + 0.5  # jitter may add .5

    assert stages[-1] <= next(backoff) <= stages[-1] + 0.5
    assert backoff.percent_to_max_time() == 1


@UnitTest
def test_backoff_percent_to_max_time_litteral() -> None:
    """Just in case a bug occurs in one of the generic tests."""
    backoff = Backoff(max_backoff_attempts=5, stages=(1, 5, 10, 15))

    def _check_for(percent_value: float, backoff_value: float) -> None:
        assert backoff.percent_to_max_time() == percent_value
        assert backoff_value <= next(backoff) <= backoff_value + 0.5

    _check_for(1 / 15, 1)
    _check_for(5 / 15, 5)
    _check_for(10 / 15, 10)

    # 5 max backoff attempts
    _check_for(1, 15)
    _check_for(1, 15)
    _check_for(1, 15)
    _check_for(1, 15)
    _check_for(1, 15)

    with pytest.raises(MaxBackoffException):
        next(backoff)
