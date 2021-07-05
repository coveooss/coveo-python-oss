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
    Tuple,
    overload,
    Final,
    cast,
    List,
)

from coveo_functools.annotations import find_annotations
from coveo_functools.casing import unflex, flexcase
from coveo_functools.dispatch import dispatch
from coveo_functools.exceptions import UnsupportedAnnotation

_ = unflex, flexcase  # mark them as used (forward compatibility vs docs)


JSON_TYPES = (str, bool, int, float, type(None))  # list omitted to support list of custom types
PASSTHROUGH_TYPES = {dict, None, Any, *JSON_TYPES}  # todo: do we really need both?

META_TYPES = (Union, Optional)

T = TypeVar("T")

SupportedTypes = Union[Type[T], Callable[..., T]]
Wrapper = Callable[..., T]
Delegate = Callable[[SupportedTypes], Wrapper]

RAW_KEY: Final[str] = "_flexed_from_"


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


def _generate_callable_wrapper(fn: Callable[..., T]) -> Callable[..., T]:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        value = fn(*args, **_remap_and_convert(fn, kwargs))
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


def _remap_and_convert(fn: Callable[..., T], dirty_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    mapped_kwargs = unflex(fn, dirty_kwargs)
    converted_kwargs = {}

    for arg_name, arg_type in find_annotations(fn).items():
        if arg_name not in mapped_kwargs:
            continue  # this may be ok, for instance if the target argument has a default
        converted_kwargs[arg_name] = deserialize(mapped_kwargs[arg_name], hint=arg_type)

    return converted_kwargs


def _resolve_hint(thing: Type) -> Tuple[Type, Tuple[Type, ...]]:
    """
    Transform e.g. List[Union[str, bool]] into (list, Union[str, bool]).
    Also validates that the annotation is supported and removes "NoneType" if present.
    """
    origin = get_origin(thing) or thing
    args = {*get_args(thing)}

    # typing implementation detail -- At runtime, Optional exists as Union[None, ...]
    assert origin is not Optional

    if origin is dict:
        # In this case, args isn't a collection of types; rather a (key_type, value_type).
        # Dict[str, Any] would therefore come out as a (Dict, Union[str, Any]) which is wrong.
        # since we don't do anything special for dicts anyway yet, drop the arg types and carry on.
        return dict, ()

    if not args.difference(PASSTHROUGH_TYPES):
        # If all containing types are passthrough types, everything shall be fine.
        return origin, tuple(args)

    # Remove NoneType if it's present. If the value is given as None, we return None, no questions asked,
    # so we really don't need to keep this information.
    args.discard(type(None))

    if len(args) < 2:
        return origin, tuple(args)

    if len(args) == 2:
        return origin, _as_union_of_thing_or_list_of_things(*args)

    raise UnsupportedAnnotation(thing)


def _as_union_of_thing_or_list_of_things(*annotation: Type) -> Tuple[Type, Type]:
    """
    Validates that the annotation accepts thing or a list of things.
    Returns the ordered args; we always move the target type to the first thing in the tuple.
    """
    if len(annotation) == 2:
        target_type: Optional[Any] = None
        container_kind: Optional[Any] = None

        for hint in annotation:
            origin = get_origin(hint)
            if origin is None:
                target_type = hint
            else:
                container_kind = origin

        if container_kind is list and target_type is not None:
            # note: ignore is required because mypy thinks this should be part of the static analysis.
            # I suppose we should create our own wrappers instead of piggy-backing on typing constructs at runtime.
            return target_type, List[target_type]  # type: ignore[valid-type]

    raise UnsupportedAnnotation(annotation)


def deserialize(value: Any, *, hint: Any = None) -> Any:
    origin, args = _resolve_hint(hint)

    if origin in PASSTHROUGH_TYPES or value is None:
        return value

    if origin is Union:
        # Unions of PASSTHROUGH_TYPES types are allowed and assumed to be in the proper type already
        if not {*args}.difference(PASSTHROUGH_TYPES):
            return value

        if len(args) == 1:
            return deserialize(value, hint=args[0])

        if len(args) == 2:
            if isinstance(value, list):
                return deserialize(value, hint=List[args[0]])  # type: ignore[valid-type]
            else:
                return deserialize(value, hint=args[0])

    if origin is list:
        args = args or cast(Tuple[Type, ...], (Any,))
        return _deserialize(value, hint=list, contains=args[0])

    if inspect.isclass(origin) and isinstance(value, origin):
        # it's a custom class and it's already converted
        return value

    # annotation arguments are not supported past this point, so we can omit them.
    return _deserialize(value, hint=origin)


@dispatch(switch_pos="hint")
def _deserialize(value: Any, *, hint: Any, contains: Optional[Type] = None) -> Any:
    if inspect.isclass(hint) and isinstance(value, dict):
        return flex(hint)(**value)

    # todo: raise?
    return value


@_deserialize.register(list)
def _deserialize_list(value: Any, *, hint: list, contains: Optional[Type] = None) -> List:
    if isinstance(value, list):
        return [deserialize(item, hint=contains) for item in value]

    # todo: raise?
    return value  # type: ignore[no-any-return]
