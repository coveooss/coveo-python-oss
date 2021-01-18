from contextlib import contextmanager
from typing import Generator, Callable, Any


@contextmanager
def finalizer(fn: Callable, *args: Any, **kwargs: Any) -> Generator[None, None, None]:
    """Generic context manager for a finalizer-like effect."""
    try:
        yield
    except BaseException as original_exception:
        # noinspection PyBroadException
        try:
            fn(*args, **kwargs)
        except BaseException:
            ...
        raise original_exception

    fn(*args, **kwargs)
