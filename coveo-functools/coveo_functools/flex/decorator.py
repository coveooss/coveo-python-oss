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

from coveo_functools.flex.deserializer import convert_kwargs_for_unpacking, ErrorBehavior

T = TypeVar("T")

RealClass = Type[T]
RealFunction = Callable[..., T]
RealObject = Union[RealClass, RealFunction]
WrappedClass = Type[T]
WrappedFunction = Callable[..., T]
WrappedObject = Union[WrappedClass, WrappedFunction]


RAW_KEY: Final[str] = "_coveo_functools_flexed_from_"


@overload
def flex(*, errors: ErrorBehavior = "deprecated") -> Callable[[RealObject], WrappedObject]:
    ...


@overload
def flex(
    obj: None, *, errors: ErrorBehavior = "deprecated"
) -> Callable[[RealObject], WrappedObject]:
    ...


@overload
def flex(obj: RealClass, *, errors: ErrorBehavior = "deprecated") -> WrappedClass:
    ...


@overload
def flex(obj: RealFunction, *, errors: ErrorBehavior = "deprecated") -> WrappedFunction:
    ...


def flex(
    obj: Optional[RealObject] = None,
    *,
    errors: ErrorBehavior = "deprecated",
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

        return _generate_wrapper(obj, errors=errors)

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
        return functools.partial(flex, errors=errors)


@overload
def _generate_wrapper(obj: RealClass, *, errors: ErrorBehavior) -> WrappedClass:
    ...


@overload
def _generate_wrapper(obj: RealFunction, *, errors: ErrorBehavior) -> WrappedFunction:
    ...


def _generate_wrapper(obj: RealObject, *, errors: ErrorBehavior) -> WrappedObject:
    """Generates a wrapper over obj."""
    # handle custom objects
    if inspect.isclass(obj):
        return _generate_class_wrapper(obj, errors=errors)

    # handle custom callables
    return _generate_callable_wrapper(obj, errors=errors)


def _generate_callable_wrapper(fn: RealFunction, errors: ErrorBehavior) -> WrappedFunction:
    """Class decorators"""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        value: T = fn(*args, **convert_kwargs_for_unpacking(kwargs, hint=fn, errors=errors))
        if hasattr(value, "__dict__"):
            value.__dict__[RAW_KEY] = kwargs
        return value

    return wrapper


def _generate_class_wrapper(obj: RealClass, *, errors: ErrorBehavior) -> WrappedClass:
    """Function decorators"""
    fn: RealFunction = obj.__init__

    @functools.wraps(fn)
    def new_init(*args: Any, **kwargs: Any) -> None:
        setattr(args[0], RAW_KEY, kwargs)  # set the raw data on self
        fn(*args, **convert_kwargs_for_unpacking(kwargs, hint=fn, errors=errors))

    obj.__init__ = new_init
    return obj
