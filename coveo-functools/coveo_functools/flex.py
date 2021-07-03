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
    cast,
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
) -> Generator[Tuple[str, Any], None, None]:

    # scan the arguments for custom types and convert them
    for arg_name, arg_type in arguments.items():
        if arg_name not in mapped_kwargs:
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
                        # todo: we should allow things like Union[T, List[T]] (one or many)
                        raise AmbiguousAnnotation(meta_type)
                    else:
                        arg_value = flex(allowed_types[0])(**mapped_kwargs[arg_name])

            # elif meta_type in (List, Set, Iterable, Collection, Sequence):
            #     ...  # handle lists/etc
            # elif meta_type in (Dict, Mapping, MutableMapping):
            #     ...  # handle mappings

            elif meta_type:
                raise FlexException(f"Unsupported type: {meta_type}")

            else:
                arg_value = flex(arg_type)(**mapped_kwargs[arg_name])

        # convert the argument to the target class
        yield arg_name, arg_value


def _remap_and_convert(obj: SupportedTypes, dirty_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    mapped_kwargs = unflex(obj, dirty_kwargs)
    return dict(_convert(find_annotations(obj), mapped_kwargs))


@overload
def _generate_wrapper(obj: Type[T]) -> Type[T]:
    ...


@overload
def _generate_wrapper(obj: Callable[..., T]) -> Callable[..., T]:
    ...


def _generate_wrapper(obj: Union[Type[T], Callable[..., T]]) -> Union[Type[T], Callable[..., T]]:
    """Returns a wrapper over _flex_call to please Python's mechanics."""
    if inspect.isclass(obj):
        return _generate_class_wrapper(cast(Type[T], obj))

    return _generate_callable_wrapper(cast(Callable[..., T], obj))


def _generate_callable_wrapper(obj: Callable[..., T]) -> Callable[..., T]:
    @functools.wraps(obj)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        value = obj(*args, **_remap_and_convert(obj, kwargs))
        if hasattr(value, "__dict__"):
            value.__dict__[RAW_KEY] = kwargs
        return value

    return wrapper


def _generate_class_wrapper(obj: Type[T]) -> Type[T]:
    fn = obj.__init__

    @functools.wraps(fn)
    def new_init(*args: Any, **kwargs: Any) -> None:
        setattr(args[0], RAW_KEY, kwargs)  # set the raw data on self
        fn(*args, **_remap_and_convert(fn, kwargs))

    obj.__init__ = new_init  # type: ignore[assignment]
    return obj


@overload
def flex() -> Delegate:
    ...


@overload
def flex(obj: None) -> Delegate:
    ...


@overload
def flex(obj: Type[T]) -> Type[T]:
    ...


@overload
def flex(obj: Callable[..., T]) -> Callable[..., T]:
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
