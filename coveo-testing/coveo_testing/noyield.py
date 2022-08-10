import functools
from typing import Callable, Any
from unittest.mock import _patch


class no_yield:  # noqa: lowercased decorator
    """
    Discards the yield return value of a `mock.patch` fixture. Usage:

        @void(mock.patch(...))
        def test_something() -> None:
            ...
    """

    def __init__(self, patch: _patch) -> None:
        # the patch_context_manager is the return value of `mock.patch(...)`.
        # It's a context manager, and it's not activated yet.
        self.patch_context_manager = patch

    def __call__(self, fn: Callable) -> Callable:
        @functools.wraps(fn)
        def _wrapper(*args: Any, **kwargs: Any) -> Any:
            # activate the mock for the duration of the test function.
            with self.patch_context_manager:
                return fn(*args, **kwargs)

        return _wrapper
