from typing import (
    Optional,
    get_args,
    get_origin,
    Tuple,
    List,
    Sequence,
)

from coveo_functools.exceptions import UnsupportedAnnotation
from coveo_functools.flex.types import TypeHint, PASSTHROUGH_TYPES


def resolve_hint(thing: TypeHint) -> Tuple[TypeHint, Sequence[TypeHint]]:
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
