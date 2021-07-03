from __future__ import annotations

import functools
import inspect
from typing import (
    Type,
    TypeVar,
    Optional,
    Any,
    get_args,
    get_origin,
    Union,
    Dict,
    Callable,
    Generator,
    Tuple,
    overload,
    Final,
)

from coveo_functools.annotations import find_annotations
from coveo_functools.casing import unflex, flexcase
from coveo_functools.exceptions import AmbiguousAnnotation, FlexException

_ = unflex, flexcase  # mark them as used (forward compatibility vs docs)


JSON_TYPES = (str, bool, int, float, type(None))
META_TYPES = (Union, Optional)

T = TypeVar("T")

SupportedTypes = Union[Type[T], Callable[..., T]]
Wrapper = Callable[..., T]
Delegate = Callable[[SupportedTypes], Wrapper]

RAW_KEY: Final[str] = "_flexed_from_"


def _convert(
    arguments: Dict[str, Type],
    mapped_kwargs: Dict[str, Any],
    raw: Dict[str, Any],
) -> Generator[Tuple[str, Any], None, None]:

    # scan the arguments for custom types and convert them
    for arg_name, arg_type in arguments.items():
        if arg_name == RAW_KEY:
            # inject the raw data as part as the constructor since it's present
            arg_value = raw

        elif arg_name not in mapped_kwargs:
            continue  # skip it; this may be ok if the target class has a default value for this arg

        elif arg_type in JSON_TYPES:
            # assume that builtin types are already converted
            arg_value = mapped_kwargs[arg_name]

        else:
            # check for special typing constructs
            meta_type = get_origin(arg_type)
            if meta_type in (Optional, Union):
                allowed_types = list(get_args(arg_type))
                if all(_type in JSON_TYPES for _type in allowed_types):
                    # all types are builtin, we expect it to be already ok; carry on
                    arg_value = mapped_kwargs[arg_name]
                else:
                    while type(None) in allowed_types:
                        allowed_types.remove(type(None))

                    if not allowed_types:
                        # not sure if this is even possible... Union[None, None] ?
                        arg_value = mapped_kwargs[arg_name]
                    elif len(allowed_types) > 1:
                        raise AmbiguousAnnotation(meta_type)
                    else:
                        arg_value = flex(allowed_types[0])(**mapped_kwargs[arg_name])

            elif meta_type:
                raise FlexException(f"Unsupported type: {meta_type}")

            else:
                arg_value = flex(arg_type)(**mapped_kwargs[arg_name])

        # convert the argument to the target class
        yield arg_name, arg_value


def _flex_call(
    obj: SupportedTypes,
    args: Any,
    dirty_kwargs: Dict[str, Any],
) -> T:
    """This method orchestrates `flexcase` to call `obj` in a recursive manner and returns the value."""
    if inspect.isclass(obj):
        to_map: Callable[..., T] = obj.__init__  # type: ignore[misc]
    else:
        assert callable(obj)
        to_map = obj

    # convert the keys casings to match the target class
    mapped_kwargs = unflex(to_map, dirty_kwargs)
    converted_kwargs: Dict[str, Any] = dict(
        _convert(find_annotations(to_map), mapped_kwargs, dirty_kwargs)
    )

    # with everything converted, create an instance of the class
    instance: T = obj(*args, **converted_kwargs)

    # (debugging commodity) inject the raw payload if it's not already there
    if hasattr(instance, "__dict__") and not hasattr(instance, RAW_KEY):
        instance.__dict__[RAW_KEY] = dirty_kwargs

    return instance


def _generate_flex_call_wrapper(obj: SupportedTypes) -> Wrapper:
    """Returns a wrapper over _flex_call to please Python's mechanics."""

    @functools.wraps(obj)
    def _flex_call_wrapper(*args: Any, **kwargs: Any) -> T:
        return _flex_call(obj, args, kwargs)

    return _flex_call_wrapper


@overload
def flex() -> Delegate:
    ...


@overload
def flex(obj: None) -> Delegate:
    ...


@overload
def flex(obj: SupportedTypes) -> Wrapper:
    ...


def flex(obj: Optional[SupportedTypes] = None) -> Union[Wrapper, Delegate]:
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

        return _generate_flex_call_wrapper(obj)

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
