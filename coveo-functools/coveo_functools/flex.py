from __future__ import annotations

import collections
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
    List,
    Sequence,
    cast,
)

from coveo_functools.annotations import find_annotations
from coveo_functools.casing import unflex, flexcase
from coveo_functools.dispatch import dispatch
from coveo_functools.exceptions import UnsupportedAnnotation

_ = unflex, flexcase  # mark them as used (forward compatibility vs docs)


JSON_TYPES = (
    str,
    bool,
    int,
    float,
    type(None),
    dict,
)  # list omitted to support list of custom types
PASSTHROUGH_TYPES = {None, Any, *JSON_TYPES}

T = TypeVar("T")

TypeHint = Any  # :shrug:

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
def deserialize(value: Any, *, hint: Type[T]) -> T:
    ...


@overload
def deserialize(value: Any, *, hint: T) -> T:
    """This overload tricks mypy in passing typing annotations as types, such as List[str]."""


def deserialize(value: Any, *, hint: Union[T, Type[T]]) -> T:
    """
    Deserializes a value based on the provided type hint:

    - If value is None, we return None. We don't validate the hint.
    - If hint is a builtin type, we blindly return the value we were given. We don't validate the value.
    - If hint is a custom class, the value must be a dictionary to "flex" into the class.
    - Hint may be a `Union[T, List[T]]`, in which case the value must be a dict or a list of them.
    """
    if value is None:
        return None  # nope!

    # origin: like `list` for `List` or `Union` for `Optional`
    # args: like (str, int) for Optional[str, int]
    origin, args = _resolve_hint(hint)
    # implementation detail: in the presence of a custom type in the args, the `_resolve_hint` function
    # always puts the real type first. This is only applicable to the thing-or-list-of-things feature.
    target_type: TypeHint = args[0] if args else Any

    if origin is Union:
        if not {*args}.difference(PASSTHROUGH_TYPES):
            # Unions of PASSTHROUGH_TYPES are allowed and assumed to be in the proper type already
            return cast(T, value)

        if len(args) == 1:
            # launch again with only that type
            return cast(T, deserialize(value, hint=args[0]))

        if len(args) == 2:
            # special support for variadic "thing-or-list-of-things" payloads is based on the type of the value.
            if _is_array_like(value):
                return cast(T, deserialize(value, hint=List[target_type]))
            else:
                return cast(T, deserialize(value, hint=target_type))

    if origin is list:
        return cast(T, _deserialize(value, hint=list, contains=target_type))

    if origin is dict:
        # json can't have maps or lists as keys, so we can't either. Ditch the key annotation, but convert values.
        return cast(T, _deserialize(value, hint=dict, contains=args[1] if args else Any))

    if origin in PASSTHROUGH_TYPES:
        # we always return those without validation
        return cast(T, value)

    if inspect.isclass(origin) and isinstance(value, origin):
        # it's a custom class and it's already converted
        return cast(T, value)

    # annotation arguments are not supported past this point, so we can omit them.
    return cast(T, _deserialize(value, hint=origin))


@dispatch(switch_pos="hint")
def _deserialize(value: Any, *, hint: TypeHint, contains: Optional[TypeHint] = None) -> Any:
    """Fallback deserialization; if dict and hint is class, flex it. Else just return value."""
    if inspect.isclass(hint) and isinstance(value, dict):
        return flex(hint)(**value)  # type: ignore[call-arg]

    return value


@_deserialize.register(list)
def _deserialize_list(value: Any, *, hint: list, contains: Optional[TypeHint] = None) -> List:
    """List deserialization into list of things."""
    if _is_array_like(value):
        return [deserialize(item, hint=contains) for item in value]

    return value  # type: ignore[no-any-return]


@_deserialize.register(dict)
def _deserialize_dict(value: Any, *, hint: dict, contains: Optional[TypeHint] = None) -> Dict:
    if isinstance(value, collections.Mapping):
        return {key: deserialize(val, hint=contains or Any) for key, val in value.items()}

    return value  # type: ignore[no-any-return]


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
        value: T = fn(*args, **_remap_and_convert(fn, kwargs))
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
        fn(*args, **_remap_and_convert(fn, kwargs))

    obj.__init__ = new_init
    return obj


def _remap_and_convert(fn: RealFunction, dirty_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Orchestrates the deserialization of `dirty_kwargs` into `fn`."""
    mapped_kwargs = unflex(fn, dirty_kwargs)
    converted_kwargs = {}

    for arg_name, arg_type in find_annotations(fn).items():
        if arg_name not in mapped_kwargs:
            continue  # this may be ok, for instance if the target argument has a default
        converted_kwargs[arg_name] = deserialize(mapped_kwargs[arg_name], hint=arg_type)

    return converted_kwargs


def _resolve_hint(thing: TypeHint) -> Tuple[TypeHint, Sequence[TypeHint]]:
    """
    Transform e.g. List[Union[str, bool]] into (list, (str, bool)) or Dict[str, Any] into (dict, (str, Any)).
    Also validates that the annotation is supported and removes "NoneType" if present.

    Some rules are enforced here:
        - It's allowed to have unions of multiple JSON types; we assume they're already converted.
        - A union containing multiple custom types is forbidden (we don't support it... yet?)
        - A union is allowed to contain a Union[List[Thing], Thing] where Thing is any custom class.
          In this case, Thing is always the first arg in the list of args.
          i.e.: we may return (Thing, List[Thing]), but never (List[Thing], Thing)
    """
    origin = get_origin(thing) or thing
    args = list(get_args(thing))

    # typing implementation detail -- At runtime, Optional exists as Union[None, ...]
    assert origin is not Optional

    if origin is dict:
        # the annotation in this case is [key, value]; they shall be reevaluated separately.
        return origin, args

    # Remove NoneType if it's present. If the value is given as None, we return None, no questions asked,
    # so we really don't need to keep this information.
    while type(None) in args:
        args.remove(type(None))

    if not set(args).difference(PASSTHROUGH_TYPES):
        # If all containing types are passthrough types, everything shall be fine.
        return origin, args

    if len(args) < 2:
        return origin, args

    if len(args) == 2:
        return origin, _as_union_of_thing_or_list_of_things(*args)

    raise UnsupportedAnnotation(thing)


def _as_union_of_thing_or_list_of_things(*annotation: TypeHint) -> Tuple[TypeHint, TypeHint]:
    """
    Validates that the annotation accepts "thing or a list of things" and returns it. Raise otherwise.
    Returns the ordered args; we always move the target type to the first thing in the tuple.
    """
    if len(annotation) == 2:
        target_type: Optional[TypeHint] = None
        container_kind: Optional[TypeHint] = None

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


def _is_array_like(thing: Any) -> bool:
    """We don't want to mix up dictionaries and strings with tuples, sets and lists."""
    return all(
        (
            isinstance(thing, collections.Iterable),
            not isinstance(thing, (str, bytes)),
            not isinstance(thing, collections.Mapping),
        )
    )
