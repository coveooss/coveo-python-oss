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
    List,
)

from coveo_functools.annotations import find_annotations
from coveo_functools.casing import unflex, flexcase
from coveo_functools.dispatch import dispatch
from coveo_functools.exceptions import FlexException, UnsupportedAnnotation

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
                        raise UnsupportedAnnotation(meta_type)
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


def _resolve_hint(thing: Type) -> Tuple[Type, Tuple[Type, ...]]:
    """
    Transform e.g. List[Union[str, bool]] into (list, Union[str, bool]).
    Also validates that the annotation is supported and removes "NoneType" if present.
    """
    origin = get_origin(thing) or thing
    args = {*get_args(thing)}

    assert (
        origin is not Optional
    ), "Unreachable code / guard; Optionals are always Unions that include None."

    if origin is dict:
        # In this case, args isn't a collection of types; rather a (key_type, value_type).
        # Dict[str, Any] would therefore come out as a (Dict, Union[str, Any]) which is wrong.
        # since we don't do anything special for dicts anyway yet, drop the arg types and carry on.
        return dict, ()

    # Remove NoneType if it's present. If the value is given as None, we return None, no questions asked,
    # so we really don't need to keep this information.
    args.discard(type(None))

    if len(args) < 2:
        return origin, tuple(args)

    if len(args) == 2:
        return origin, _as_union_of_thing_or_list_of_things(*args)

    # Unions of various PASSTHROUGH_TYPES are allowed (we expect them to be converted already e.g. json.load)
    if not args.difference(PASSTHROUGH_TYPES):
        return origin, tuple(args)

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


# @_deserialize.register(dict)
# def _deserialize_dict(value: Dict[str, Any], *, hint: Type[dict]) -> Dict[str, Any]:
#     if isinstance(hint, GenericMeta):
#         # py3.6 path
#         # noinspection PyUnresolvedReferences
#         item_type = hint.__args__[1] if hint.__args__ else None
#         try:
#             return {key: deserialize(value, hint=item_type) for key, value in value.items()}
#         except AttributeError:
#             print("!")
#
#     # noinspection PyArgumentList
#     return hint((k, deserialize(v)) for k, v in value.items())


# @_deserialize.register(list)
# def _deserialize_list(value: List[Any], *, hint: Type[list]) -> List:
#     if isinstance(value, str):
#         raise ValueError
#
#     if isinstance(hint, GenericMeta):
#         # py3.6 path
#         # noinspection PyUnresolvedReferences
#         item_type = hint.__args__[0] if hint.__args__ else None
#         return [deserialize(v, hint=item_type) for v in value]
#
#     # noinspection PyArgumentList
#     return hint(deserialize(v) for v in value)
#
#
# @_deserialize.register(JidType)
# def _deserialize_jid_type(value: Dict[str, Any], *, hint: Type[JidType]) -> JidType:
#     """Most cases should be handled by the shortcircuit in _deserialize; this one handles cases where the
#     service returns a correctly formatted object without a _type hint."""
#     if isinstance(value, JidType):
#         return value
#
#     if hint is JidType or not issubclass(hint, JidType):
#         raise TypeError(f'Unable to infer JidType: {value}')
#
#     return flexcase(hint)(**{k: v for k, v in value.items() if v is not None})
#
#
# @_deserialize.register(FunctionType)
# @_deserialize.register(MethodType)
# def _deserialize_from_callable(value: Dict[str, Any], *, hint: Callable) -> Dict[str, Any]:
#     """Use annotations from fn to deserialize value. Extra args will be stripped out and casing is flexible."""
#     assert isinstance(value, dict)
#     value = unflex(hint, value)  # fix the case of keys in value
#     for argument_name, annotation in find_annotations(hint).items():
#         if argument_name == 'return':
#             continue
#         # set the deserialized value
#         value[argument_name] = deserialize(value[argument_name], hint=annotation)
#     return value
#
#
# @_deserialize.register(datetime)
# def _deserialize_datetime(value: float, *, hint: Type[datetime]) -> datetime:
#     if isinstance(value, datetime):
#         return value
#     return hint.utcfromtimestamp(value)
#
#
# # @__deserialize.register(StringEnum)
# @_deserialize.register(JidEnumFlag)
# def _deserialize_enum(value: str, *, hint: Type[JidEnumFlag]) -> JidEnumFlag:
#     if isinstance(value, JidEnumFlag):
#         return value
#
#     if isinstance(value, list) and len(value) == 1:
#         # in SOAP, these are contained within a list.
#         value = value[0]
#
#     if isinstance(value, int):
#         # noinspection PyArgumentList
#         return hint(value)
#
#     value = value.replace('None', 'None_')
#
#     if '+' in value:
#         # noinspection PyArgumentList
#         return functools.reduce(
#             lambda x, y: x | y,
#             (hint[flag] for flag in value.split('+')))
#
#     # noinspection PyArgumentList
#     try:
#         return hint[value]
#     except KeyError as ex:
#         if value.isnumeric():
#             # noinspection PyArgumentList
#             return hint(int(value))
#         raise ex


def _deserialize_normalized(
    value: Any, outer_type: Type[T], inner_type: Optional[Type] = None
) -> T:
    ...
