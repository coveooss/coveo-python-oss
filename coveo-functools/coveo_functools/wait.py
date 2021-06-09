""" The friendly wait-for-it helper """

from collections.abc import Iterator
from datetime import timedelta, datetime
from time import sleep
from typing import Callable, Any, Union, Tuple, Type, Optional, Generator
from random import random

ExceptionHandling = Tuple[Type[Exception], ...]
SuppressCondition = Union[bool, Type[Exception], Tuple[Type[Exception], ...]]
TimeoutValue = Union[float, int, timedelta]
NaiveCallback = Callable[[], None]


class TimeoutExpired(Exception):
    """Exception denotes a timeout waiting for a condition."""


class MaxBackoffException(StopIteration):
    """When we're all out of bubble gum."""


def until(
    condition: Callable[[], Any],
    timeout_s: Optional[TimeoutValue] = 300,
    retry_ms: Optional[TimeoutValue] = 500,
    handle_exceptions: SuppressCondition = None,
    failure_message: str = None,
) -> None:
    """
    Waits for a condition to be True, or raise a TimeoutException.

    condition: An expression that returns a trueish-testable value.

    timeout_s: The allocated time for the condition to be met. Use timeout(0) or None to wait indefinitely.
     If you pass an int/float, it will be resolved to seconds.

    retry_ms: The time to wait between failed attempts.
     If you pass an int/float, it will be resolved to milliseconds.
     If <=0, retry as fast as possible.

    handle_exceptions: Controls what happens when the wait condition raises an exception.
        - None: Let them raise!
        - True: Silence them all. Whatever happens, wait for timeout and raise a TimeoutException.
        - Exception type or tuple of exception types: Ignore these exceptions, raise on any other.

    failure_message: Customize the message to display within the TimeoutException.
    """
    # convert timeout/retry to timedelta
    if not isinstance(timeout_s, timedelta):
        timeout_s = timedelta(seconds=timeout_s or 0)
    if not isinstance(retry_ms, timedelta):
        retry_ms = timedelta(milliseconds=retry_ms or 0)

    def _get_exception_tuple(suppress_condition: Optional[SuppressCondition]) -> ExceptionHandling:
        """Constructs an exception tuple that defines which exceptions to handle/retry within the timeout loop."""
        if suppress_condition in (None, False):
            return ()
        if suppress_condition is True:
            return (Exception,)
        if isinstance(suppress_condition, type) and issubclass(suppress_condition, Exception):
            return (suppress_condition,)
        if isinstance(suppress_condition, tuple):
            return suppress_condition
        raise ValueError(f"Unsupported suppress condition: {suppress_condition}")

    suppressed_exceptions = _get_exception_tuple(handle_exceptions)

    infinite = not timeout_s  # enable infinite looping?
    if not infinite:
        retry_ms = min(timeout_s, retry_ms)  # ensure retry is not larger than timeout

    last_value: Any = None
    zero = timedelta()

    while infinite or timeout_s >= zero:
        call_timestamp = datetime.now()
        sleep_time = retry_ms
        try:
            last_value = condition()
            if last_value:  # win!
                return

        except suppressed_exceptions as timeout_exception:
            last_value = timeout_exception  # keep it for later

        if not infinite:
            elapsed = datetime.now() - call_timestamp
            sleep_time = max(
                zero, retry_ms - elapsed
            )  # sleep time is reduced by call time because why not.
            timeout_s -= elapsed + sleep_time

        if timeout_s >= zero:  # don't sleep if timeout already drained out
            sleep(sleep_time.total_seconds())

    timeout_message = failure_message or f"Timed out waiting for condition: {last_value}"
    if isinstance(last_value, Exception):
        raise TimeoutExpired(timeout_message) from last_value
    raise TimeoutExpired(timeout_message)


class Backoff(Iterator):
    """
    Utility class that helps with backoff strategies. All time-related floats are expressed in seconds.

    This iterator resets after StopIteration, so it can be used again. It's also possible to reset it manually by
    calling reset().

    -- loop failure management
        backoff = Backoff()
        while my_loop:
            try:
                do_stuff()
            except Exception as exception:
                try:
                    quit_flag.wait(next(backoff))
                except backoff.RetriesExhausted:
                    raise exception

    -- alternate try/catch block example:
        wait_time = next(backoff, None)
        if wait_time is None:
            raise exception
        quit_flag.wait(wait_time)

    -- you can use it as a tool to generate the various wait stages, but in that case you lose max_backoff_attempts:
        wait_times = list(Backoff.generate_backoff_stages(first_wait, growth, max_backoff))
        for sleep_time in wait_times:
            try:
                do_stuff()
                break
            except:
                time.sleep(sleep_time)
        else:
            raise ImSickOfTrying()
    """

    def __init__(
        self,
        first_wait: float = 0.2,
        max_backoff: float = 30,
        max_backoff_attempts: Optional[int] = 4,
        growth: float = 2.5,
        *,
        stages: Tuple[float, ...] = None,
    ) -> None:
        """
        Initializes a backoff helper. The default values provide 10 retries of these approximate lengths:
            [0.2, 0.5, 1.25, 3.1, 7.8, 19.5, 30, 30, 30, 30]

        :param first_wait: The time to wait on the first retry.
        :param max_backoff: The maximum time to wait (truncated backoff).
        :param max_backoff_attempts: The amount of times we're allowed to wait max_backoff before StopIteration.
                                     Set to None for infinite backoff.

        :param growth: Wait time is cumulatively * by this amount every time next() is called.
        :param stages: You can specify the wait seconds yourself e.g.: (1, 2, 4, 5) instead of
                       specifying firstwait/maxbackoff/growth.
        """
        self.stage: int = 0
        self._stages = stages or tuple(
            self.generate_backoff_stages(first_wait, growth, max_backoff)
        )
        if not self._stages or (0 in self._stages):
            raise ValueError("Backoff received wrong values.")

        # ex: given stages: (1, 2, 4, 5)
        if not max_backoff_attempts:
            self._max_stage = 0  # disabled, will repeat max backoff infinitely.
        else:
            # given max_backoff 5 we do 4+4: (1, 2, 4, 5) + (5, 5, 5, 5)
            self._max_stage = len(self._stages) + abs(max_backoff_attempts) - 1

    def percent_to_max_time(self) -> float:
        """
        0.5 would mean that the next waiting time will be 50% of the max
        amount of time we're allowed to wait. e.g.:

        Given stages (1, 2, 4, 5)
            - 1.0 is 5 seconds
            - 0.8 is 4 seconds
            - 0.4 is 2 seconds
            - 0.2 is one second

        Technically, 0 cannot be returned.

        This can be used to fire up warnings and alerts early.
        """
        next_stage = min(self.stage, len(self._stages) - 1)
        return self._stages[next_stage] / self._stages[-1]

    @staticmethod
    def generate_backoff_stages(
        first_wait: float, growth: float, max_backoff: float
    ) -> Generator[float, None, None]:
        """Generate the stages (wait seconds) of this backoff strategy."""
        # Any invalid value is adjusted to sane defaults. This is a safeguard in case one of the values comes from
        # the environment or command line to prevent infinite backoff.
        first_wait = abs(first_wait) or 0.2
        max_backoff = abs(max_backoff) or 4
        growth = growth if growth > 1 else 2

        wait = first_wait

        while wait < max_backoff:
            yield wait
            wait = min(wait * growth, max_backoff)

        yield max_backoff

    def __next__(self) -> float:
        """
        Returns a float that indicates how much time to wait, or raise StopIteration if
        max_backoff_attempts has been reached.
        """
        # check if we're at max_attempts
        if self._max_stage and self.stage >= self._max_stage:
            self.reset()
            raise MaxBackoffException

        # identify current wait time.
        this_wait = self._stages[min(len(self._stages) - 1, self.stage)]

        # jitter by 50% (up to 500ms), but not on the first attempt.
        jitter = (random() * min(this_wait * 0.5, 0.5)) if self.stage else 0

        self.stage += 1
        return this_wait + jitter

    def reset(self) -> None:
        """Resets the stage to 0."""
        self.stage = 0


class NoBackoff(Backoff):
    """
    A special backoff strategy that immediately raises RetriesExhausted. This is a convenience class that makes code
    cleaner compared to Optional[Backoff].
    """

    def __next__(self) -> float:
        """Raise immediately, as if all retries were exhausted."""
        raise MaxBackoffException

    def __bool__(self) -> bool:
        """It's the only false backoff ever."""
        return False
