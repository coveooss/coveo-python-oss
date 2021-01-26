"""singledispatch is too young and needs a little help..."""


from functools import singledispatch as _singledispatch, update_wrapper
import inspect
from typing import Any, Type, cast, Union, Callable, TypeVar
from typing_extensions import Protocol

T = TypeVar("T")


class SingleDispatch(Protocol[T]):
    def register(*args: Any, **kwargs: Any) -> "SingleDispatch[T]":
        ...

    def __call__(*args: Any, **kwargs: Any) -> T:
        ...


class _Dispatch:
    def __init__(self, *, switch_pos: Union[int, str] = 0) -> None:
        self.switch_pos = switch_pos

    def __call__(self, func: Callable[..., T]) -> SingleDispatch[T]:
        """This is an enhanced version of @singledispatch:
        - adds support for types
        - not limited to switch pos 0
        - can target kwargs
        """
        dispatcher = _singledispatch(func)
        signature = inspect.signature(func)
        switch_keyword = (
            list(signature.parameters.keys())[self.switch_pos]
            if isinstance(self.switch_pos, int)
            else self.switch_pos
        )

        def _wrapper(*args: Any, **kw: Any) -> T:
            switch = signature.bind(*args, **kw).arguments[switch_keyword]
            dispatch_type: Type = switch if isinstance(switch, type) else switch.__class__
            return dispatcher.dispatch(dispatch_type)(*args, **kw)

        # noinspection PyTypeHints
        _wrapper.register = dispatcher.register  # type: ignore
        update_wrapper(_wrapper, func)
        return cast(SingleDispatch[T], _wrapper)


def _register_warning(*_: Any, **__: Any) -> None:
    """A common mistake is to use @dispatch() then @dispatch.register(), we give a hint to the dev in this case."""
    raise TypeError(
        """register(...) must be called from the wrapper and not from @dispatch:

@dispatch()
def some_method(arg):
    ...

@some_method.register(int)
@some_method.register(bool)
def _dispatch_ints_and_bools(arg):
    ...

"""
    )


# this hides our "fake" register method from pycharm's auto-completion so not to provoke more mistakes.
# noinspection PyTypeHints
_Dispatch.register = _register_warning  # type: ignore


dispatch = _Dispatch
