from __future__ import annotations

import functools
import inspect
from typing import (
    TypeVar,
    Optional,
    Any,
    Union,
    Callable,
    overload,
    Final,
    Type,
)

from coveo_functools.flex.deserializer import prepare_payload_for_unpacking


T = TypeVar("T")

RealClass = Type[T]
RealFunction = Callable[..., T]
RealObject = Union[RealClass, RealFunction]
WrappedClass = Type[T]
WrappedFunction = Callable[..., T]
WrappedObject = Union[WrappedClass, WrappedFunction]


RAW_KEY: Final[str] = "_coveo_functools_flexed_from_"


@overload
def flex() -> Callable[[RealObject], WrappedObject]:
    ...


@overload
def flex(obj: None) -> Callable[[RealObject], WrappedObject]:
    ...


@overload
def flex(obj: RealClass) -> WrappedClass:
    ...


@overload
def flex(obj: RealFunction) -> WrappedFunction:
    ...


def flex(
    obj: Optional[RealObject] = None,
) -> Union[WrappedObject, Callable[[RealObject], WrappedObject]]:
    """Wraps `obj` into recursive flexcase magic."""
    if obj is not None:

        """
        Covers decorator usages without parenthesis:

            @flex
            def obj(...)

            @flex
            class C:
                @flex
                def obj(self, ...)
                    ...

        Also covers the complete inline usage:

            f = flex(obj, ...)(**dirty_kwargs)

        """

        return _generate_wrapper(obj)

    else:

        """
        Covers decorator usages with parenthesis:

            @flex()
            def obj(...)

            @flex()
            class C:

                @flex()
                def obj(self, ...)
                    ...
        """

        # python's mechanic is going to call us again with the obj as the first (and only) argument to get a wrapper.
        return flex


@overload
def _generate_wrapper(obj: RealClass) -> WrappedClass:
    ...


@overload
def _generate_wrapper(obj: RealFunction) -> WrappedFunction:
    ...


def _generate_wrapper(obj: RealObject) -> WrappedObject:
    """Generates a wrapper over obj."""
    # handle custom objects
    if inspect.isclass(obj):
        return _generate_class_wrapper(obj)  # type: ignore[arg-type]

    # handle custom callables
    return _generate_callable_wrapper(obj)


def _generate_callable_wrapper(fn: RealFunction) -> WrappedFunction:
    """Class decorators"""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        value: T = fn(*args, **prepare_payload_for_unpacking(fn, kwargs))
        if hasattr(value, "__dict__"):
            value.__dict__[RAW_KEY] = kwargs
        return value

    return wrapper


def _generate_class_wrapper(obj: RealClass) -> WrappedClass:
    """Function decorators"""
    fn: RealFunction = obj.__init__

    @functools.wraps(fn)
    def new_init(*args: Any, **kwargs: Any) -> None:
        setattr(args[0], RAW_KEY, kwargs)  # set the raw data on self
        fn(*args, **prepare_payload_for_unpacking(fn, kwargs))

    obj.__init__ = new_init
    return obj
