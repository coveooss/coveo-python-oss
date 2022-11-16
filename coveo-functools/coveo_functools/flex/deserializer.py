import inspect
import logging
import warnings
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
    Tuple,
    Literal,
)

from coveo_functools.annotations import find_annotations
from coveo_functools.casing import TRANSLATION_TABLE, unflex
from coveo_functools.dispatch import dispatch
from coveo_functools.exceptions import UnsupportedAnnotation, PayloadMismatch
from coveo_functools.flex.factory_adapter import get_factory_adapter
from coveo_functools.flex.helpers import resolve_hint
from coveo_functools.flex.serializer import SerializationMetadata
from coveo_functools.flex.subclass_adapter import get_subclass_adapter
from coveo_functools.flex.types import TypeHint, is_passthrough_type, PASSTHROUGH_TYPES


T = TypeVar("T")

MetaHint = Union[Callable[..., T], SerializationMetadata, Type[T]]
ErrorBehavior = Literal["raise", "ignore", "silent", "deprecated"]


def convert_kwargs_for_unpacking(
    dirty_kwargs: Dict[str, Any], *, hint: MetaHint, errors: ErrorBehavior = "deprecated"
) -> Dict[str, Any]:
    """Return a copy of `dirty_kwargs` that can be `**unpacked` to hint. Values will be deserialized recursively."""
    # start by determining what fn should be based on the hint
    additional_metadata: Dict[str, SerializationMetadata] = {}
    if isinstance(hint, SerializationMetadata):
        fn: Callable[..., T] = hint.import_type().__init__
        # the additional metadata will be applied on the arguments of `fn` and may contain more specific type info
        additional_metadata = hint.additional_metadata
    elif inspect.isclass(hint):
        fn = hint.__init__
    else:
        fn = hint

    # clean the casing of the kwargs so they match fn's argument names.
    mapped_kwargs = unflex(fn, dirty_kwargs)

    # convert the values so they match the additional metadata if available, else fn's annotations.
    converted_kwargs = {}
    for arg_name, arg_hint in {**find_annotations(fn), **additional_metadata}.items():  # type: ignore[arg-type]
        if arg_name not in mapped_kwargs:
            continue  # this may be ok, for instance if the target argument has a default

        converted_kwargs[arg_name] = deserialize(
            mapped_kwargs[arg_name], hint=arg_hint, errors=errors
        )

    return converted_kwargs


@overload
def deserialize(
    value: Any,
    *,
    hint: Type[T],
    errors: ErrorBehavior = "deprecated",
) -> T:
    ...


@overload
def deserialize(
    value: Any,
    *,
    hint: T,
    errors: ErrorBehavior = "deprecated",
) -> T:
    """This overload tricks mypy in passing typing annotations as types, such as List[str]."""


def deserialize(
    value: Any,
    *,
    hint: Union[T, Type[T]],
    errors: ErrorBehavior = "deprecated",
) -> T:
    """
    Deserializes a value based on the provided type hint:

    - If value is None, we return None. We don't validate the hint.
    - If hint is a builtin type, we blindly return the value we were given. We don't validate the value.
    - If hint is a custom class, the value must be a dictionary to "flex" into the class.
    - Hint may be a `Union[T, List[T]]`, in which case the value must be a dict or a list of them.

    The `errors` argument controls the behavior when a value cannot be deserialized into the hint or annotation:
        - 'ignore': the value is used as-is, without deserialization. errors will be logged.
        - 'silent': behave like 'ignore' but don't log errors  # yolo
        - 'raise': raise a PayloadMismatch exception.
        - 'deprecated': (default) different situations yield different behaviors:
            - type mismatch between value and hint (e.g.: cannot use a list to create a dict) would behave like 'ignore'
            - value mismatch (e.g.: dict missing some arguments vs a class's __init__) would raise TypeError

    Note that the `deprecated` option is currently the default, for legacy reasons. It will be removed because
    it created an inconsistent behavior (see the examples below).

    example #1: `range` requires the `stop` argument, which is missing:

        >>> deserialize({}, hint=range, errors='raise')  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        TypeError: range expected 1 argument, got 0
        >>> deserialize({}, hint=range, errors='deprecated')  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        TypeError: range expected 1 argument, got 0
        >>> deserialize({}, hint=range, errors='ignore')
        {}

    example #2: the hint is a dict, but a list was provided:

        >>> deserialize([], hint=dict, errors='raise')  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        coveo_functools.exceptions.PayloadMismatch: I don't know how to fit <class 'list'> into <class 'dict'> of typing.Any
        >>> deserialize([], hint=dict, errors='deprecated')
        []
        >>> deserialize([], hint=dict, errors='ignore')
        []
    """
    valid_error_modes = "raise", "ignore", "silent", "deprecated"
    if errors not in valid_error_modes:
        raise ValueError(f"'{errors=}' is not valid, {valid_error_modes=}")

    if errors == "deprecated":
        warnings.warn(
            "Please specify the error behavior when calling `flex.deserialize`. "
            "Recommended fix: specify `errors='raise'` to catch deserialization errors. ",
            category=DeprecationWarning,
        )

    if value is None:
        return value

    if adapter := get_subclass_adapter(hint):
        # ask the adapter what the hint should be for this value
        hint = adapter(value)

    elif factory := get_factory_adapter(hint):
        # factories are expected to return an instance of the correct type, so we can just bypass everything else.
        return cast(T, factory(value))

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
            return cast(T, deserialize(value, hint=args[0], errors=errors))

        if len(args) == 2:
            # special support for variadic "thing-or-list-of-things" payloads is based on the type of the value.
            if _is_array_like(value):
                return cast(T, deserialize(value, hint=List[target_type], errors=errors))
            else:
                return cast(T, deserialize(value, hint=target_type, errors=errors))

    try:
        if origin is list:
            return cast(T, _deserialize(value, hint=list, errors=errors, contains=target_type))

        if origin is dict:
            # json can't have maps or lists as keys, so we can't either. Ditch the key annotation, but convert values.
            return cast(
                T, _deserialize(value, hint=dict, errors=errors, contains=args[1] if args else Any)
            )

        if is_passthrough_type(origin):
            # we always return those without validation
            return cast(T, value)

        if inspect.isclass(origin) and isinstance(value, origin):
            # it's a custom class and it's already converted
            return cast(T, value)

        # annotation arguments are not supported past this point, so we can omit them.
        return cast(T, _deserialize(value, hint=origin, errors=errors))

    except (PayloadMismatch, TypeError) as exception:
        if errors == "raise":
            raise

        if errors == "deprecated" and not isinstance(exception, PayloadMismatch):
            # legacy behavior: we did not handle these exceptions, raise it just like before.
            raise

        if errors != "silent":
            logging.exception(
                "An error occurred during deserialization.",
                extra={"value": value, "origin": origin, "origin_contains": args},
            )

        return value  # type: ignore[no-any-return]


@dispatch(switch_pos="hint")
def _deserialize(
    value: Any, *, hint: TypeHint, errors: ErrorBehavior, contains: Optional[TypeHint] = None
) -> Any:
    """Fallback deserialization; if value is dict and hint is callable, flex it. Else just return value."""
    if callable(hint) and isinstance(value, dict):
        return hint(**convert_kwargs_for_unpacking(value, hint=hint, errors=errors))

    raise PayloadMismatch(value, hint, contains)


@_deserialize.register(str)
@_deserialize.register(int)
@_deserialize.register(bytes)
@_deserialize.register(float)
def _deserialize_immutable(
    value: Any,
    *,
    hint: Union[Type[str], Type[int], Type[bytes], Type[float]],
    errors: ErrorBehavior,
    contains: Optional[TypeHint] = None,
) -> Union[str, int, bytes, float]:
    """If the hint is a type that subclasses an immutable builtin, convert it."""
    # note: the actual builtins are skipped early and won't call this method. See `is_passthrough_type`.
    return hint(value)


@_deserialize.register(list)
def _deserialize_list(
    value: Any, *, hint: Type[list], errors: ErrorBehavior, contains: Optional[TypeHint] = None
) -> List:
    """List deserialization into list of things."""
    if _is_array_like(value):
        return [deserialize(item, hint=contains, errors=errors) for item in value]

    raise PayloadMismatch(value, hint, contains)


@_deserialize.register(dict)
def _deserialize_dict(
    value: Any, *, hint: Type[dict], errors: ErrorBehavior, contains: Optional[TypeHint] = None
) -> Dict:
    if isinstance(value, abc.Mapping):
        return {
            key: deserialize(val, hint=contains or Any, errors=errors) for key, val in value.items()
        }

    raise PayloadMismatch(value, hint, contains)


def _flex_translate(string: str) -> str:
    return string.casefold().translate(TRANSLATION_TABLE)


@_deserialize.register(Enum)
def _deserialize_enum(
    value: Any, *, hint: Type[Enum], errors: ErrorBehavior, contains: Optional[TypeHint] = None
) -> Enum:
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
        for enum_name, enum_instance in cast(Iterable[Tuple[str, Enum]], hint.__members__.items()):
            if (
                # fish for value typos first
                (
                    isinstance(enum_instance.value, str)
                    and _flex_translate(enum_instance.value) == simplekey
                )
                # then look if the enum names look like it would match
                or _flex_translate(enum_name) == simplekey
            ):
                return enum_instance

    raise PayloadMismatch(value, hint, contains)


@_deserialize.register(SerializationMetadata)
def _deserialize_with_metadata(
    value: Any,
    *,
    hint: SerializationMetadata,
    errors: ErrorBehavior,
    contains: Optional[TypeHint] = None,
) -> Any:

    if isclass(hint) and issubclass(hint, SerializationMetadata):
        # this is an edge case; the dispatch will end up here when hint is either the SerializationMetadata type,
        # or an instance thereof.
        # Here, we take a shortcut to deserialize `value` into an instance of `SerializationMetadata`.
        # This happens when flex is also used to serialize the metadata headers.
        return hint(**convert_kwargs_for_unpacking(value, hint=hint))  # type: ignore[misc]

    root_type = hint.import_type()

    if root_type is dict:
        # each value is converted to the type provided in the meta
        return {
            key: deserialize(value, hint=hint.additional_metadata.get(key, value), errors=errors)
            for key, value in value.items()
        }

    if root_type is list:
        # the value in this case is a Dict[str, SerializationMetadata] where they key is the index within the list.
        return [
            deserialize(value[int(index)], hint=hint.additional_metadata[index], errors=errors)
            for index in sorted(hint.additional_metadata, key=int)
        ]

    if isclass(root_type) and isinstance(value, dict):
        # typical case of unpacking value into an instance of the root type.
        return root_type(
            **convert_kwargs_for_unpacking(value, hint=hint)
        )  # it's magic!  # type: ignore[no-any-return]

    if root_type is not SerializationMetadata:
        # the hint was refined this turn, we can deserialize again
        return deserialize(value, hint=root_type, errors=errors)

    raise PayloadMismatch(value, hint, contains)


def _is_array_like(thing: Any) -> bool:
    """We don't want to mix up dictionaries and strings with tuples, sets and lists."""
    return all(
        (
            isinstance(thing, abc.Iterable),
            not isinstance(thing, (str, bytes)),
            not isinstance(thing, abc.Mapping),
        )
    )
