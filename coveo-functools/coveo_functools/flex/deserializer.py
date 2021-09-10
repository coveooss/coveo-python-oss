import inspect
from collections import abc
from enum import Enum
from inspect import isabstract, isclass
from typing import (
    Type,
    TypeVar,
    Optional,
    Any,
    Union,
    Dict,
    overload,
    List,
    cast,
    Iterable,
    Callable,
)

from coveo_functools.annotations import find_annotations
from coveo_functools.casing import TRANSLATION_TABLE, unflex
from coveo_functools.dispatch import dispatch
from coveo_functools.exceptions import UnsupportedAnnotation
from coveo_functools.flex.helpers import resolve_hint
from coveo_functools.flex.serializer import SerializationMetadata
from coveo_functools.flex.subclass_adapter import get_subclass_adapter
from coveo_functools.flex.types import TypeHint, is_passthrough_type, PASSTHROUGH_TYPES


T = TypeVar("T")

MetaHint = Union[Callable[..., T], SerializationMetadata, Type[T]]


def convert_kwargs_for_unpacking(dirty_kwargs: Dict[str, Any], *, hint: MetaHint) -> Dict[str, Any]:
    """Return a copy of `dirty_kwargs` that can be `**unpacked` to hint. Values will be deserialized recursively."""
    # start by determining what fn should be based on the hint
    additional_metadata: Dict[str, SerializationMetadata] = {}
    if isinstance(hint, SerializationMetadata):
        fn: Callable[..., T] = hint.import_type().__init__
        # the additional metadata will be applied on the arguments of `fn` and may contain more specific type info
        additional_metadata = hint.additional_metadata
    elif inspect.isclass(hint):
        fn = hint.__init__  # type: ignore[misc]
    else:
        fn = hint

    # clean the casing of the kwargs so they match fn's argument names.
    mapped_kwargs = unflex(fn, dirty_kwargs)

    # convert the values so they match the additional metadata if available, else fn's annotations.
    converted_kwargs = {}
    for arg_name, arg_hint in {**find_annotations(fn), **additional_metadata}.items():  # type: ignore[arg-type]
        if arg_name not in mapped_kwargs:
            continue  # this may be ok, for instance if the target argument has a default

        converted_kwargs[arg_name] = deserialize(mapped_kwargs[arg_name], hint=arg_hint)

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
    origin, args = resolve_hint(hint)
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

    if is_passthrough_type(origin):
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
        return hint(**convert_kwargs_for_unpacking(value, hint=hint))

    return value


@_deserialize.register(list)
def _deserialize_list(value: Any, *, hint: Type[list], contains: Optional[TypeHint] = None) -> List:
    """List deserialization into list of things."""
    if _is_array_like(value):
        return [deserialize(item, hint=contains) for item in value]

    return value  # type: ignore[no-any-return]


@_deserialize.register(dict)
def _deserialize_dict(value: Any, *, hint: Type[dict], contains: Optional[TypeHint] = None) -> Dict:
    if isinstance(value, abc.Mapping):
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


@_deserialize.register(SerializationMetadata)
def _deserialize_with_metadata(
    value: Any, *, hint: SerializationMetadata, contains: Optional[TypeHint] = None
) -> Any:

    if isclass(hint) and issubclass(hint, SerializationMetadata):  # type: ignore[arg-type]
        # this is an edge case; the dispatch will end up here when hint is either the SerializationMetadata type,
        # or an instance thereof.
        # Here, we take a shortcut to deserialize `value` into an instance of `SerializationMetadata`.
        # This happens when flex is also used to serialize the metadata headers.
        return hint(**convert_kwargs_for_unpacking(value, hint=hint))  # type: ignore[operator]

    root_type = hint.import_type()

    if root_type is dict:
        # each value is converted to the type provided in the meta
        return {
            key: deserialize(value, hint=hint.additional_metadata.get(key, value))
            for key, value in value.items()
        }

    if root_type is list:
        # the value in this case is a Dict[int, SerializationMetadata] where int is the index within the list.
        return [
            deserialize(value[index], hint=hint.additional_metadata[index])
            for index in sorted(hint.additional_metadata)
        ]

    if issubclass(root_type, Enum):
        # special handling for enums.
        return deserialize(value, hint=root_type)

    if isclass(root_type) and isinstance(value, dict):
        # typical case of unpacking value into an instance of the root type.
        return root_type(
            **convert_kwargs_for_unpacking(value, hint=hint)
        )  # it's magic!  # type: ignore[no-any-return]

    return value


def _is_array_like(thing: Any) -> bool:
    """We don't want to mix up dictionaries and strings with tuples, sets and lists."""
    return all(
        (
            isinstance(thing, abc.Iterable),
            not isinstance(thing, (str, bytes)),
            not isinstance(thing, abc.Mapping),
        )
    )
