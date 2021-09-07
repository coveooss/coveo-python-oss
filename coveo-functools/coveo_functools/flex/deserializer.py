import collections
import inspect
from enum import Enum
from inspect import isabstract
from typing import (
    Type,
    TypeVar,
    Optional,
    Any,
    get_args,
    get_origin,
    Union,
    Dict,
    Tuple,
    overload,
    List,
    Sequence,
    cast,
    Iterable,
    Callable,
)

from coveo_functools.annotations import find_annotations
from coveo_functools.casing import TRANSLATION_TABLE, unflex
from coveo_functools.dispatch import dispatch
from coveo_functools.exceptions import UnsupportedAnnotation
from coveo_functools.flex.subclass_adapter import get_subclass_adapter
from coveo_functools.flex.types import TypeHint, PASSTHROUGH_TYPES


T = TypeVar("T")


def prepare_payload_for_unpacking(
    fn: Callable[..., T], dirty_kwargs: Dict[str, Any]
) -> Dict[str, Any]:
    """Return a copy of `dirty_kwargs` that can be `**unpacked` to fn()."""
    mapped_kwargs = unflex(fn, dirty_kwargs)
    converted_kwargs = {}

    for arg_name, arg_type in find_annotations(fn).items():
        if arg_name not in mapped_kwargs:
            continue  # this may be ok, for instance if the target argument has a default
        converted_kwargs[arg_name] = deserialize(mapped_kwargs[arg_name], hint=arg_type)

    return converted_kwargs


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

    if adapter := get_subclass_adapter(hint):
        # ask the adapter what the hint should be for this value
        hint = adapter(value)

    if isabstract(hint):
        raise UnsupportedAnnotation(
            f"{hint} is abstract and cannot be instantiated."
            " To use abstract classes with flex, register a subclass adapter for this abstract type:"
            " https://github.com/coveooss/coveo-python-oss/tree/main/coveo-functools#subclassadapters"
        )

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
    """Fallback deserialization; if value is dict and hint is class, flex it. Else just return value."""
    if inspect.isclass(hint) and isinstance(value, dict):
        return hint(**prepare_payload_for_unpacking(hint.__init__, value))

    return value


@_deserialize.register(list)
def _deserialize_list(value: Any, *, hint: Type[list], contains: Optional[TypeHint] = None) -> List:
    """List deserialization into list of things."""
    if _is_array_like(value):
        return [deserialize(item, hint=contains) for item in value]

    return value  # type: ignore[no-any-return]


@_deserialize.register(dict)
def _deserialize_dict(value: Any, *, hint: Type[dict], contains: Optional[TypeHint] = None) -> Dict:
    if isinstance(value, collections.Mapping):
        return {key: deserialize(val, hint=contains or Any) for key, val in value.items()}

    return value  # type: ignore[no-any-return]


def _flex_translate(string: str) -> str:
    return string.casefold().translate(TRANSLATION_TABLE)


@_deserialize.register(Enum)
def _deserialize_enum(value: Any, *, hint: Type[Enum], contains: Optional[TypeHint] = None) -> Enum:
    try:
        # value match
        return hint(value)
    except ValueError:
        pass

    try:
        # name match
        return hint[value]
    except KeyError:
        pass

    if isinstance(value, str):
        # fish!
        simplekey = _flex_translate(value)
        for enum_item in cast(Iterable[Enum], hint):
            if (
                # fish for value typos first
                (isinstance(enum_item.value, str) and _flex_translate(enum_item.value) == simplekey)
                # then look if the enum names look like it would match
                or _flex_translate(enum_item.name) == simplekey
            ):
                return enum_item

    return value  # type: ignore[no-any-return]


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
