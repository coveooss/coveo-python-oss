"""Annotation-related utilities."""


import sys
from typing import Type, Dict, get_type_hints, Callable, Union, Any


def find_annotations(
    thing: Union[Type, Callable], globalns: Dict[str, Any] = None
) -> Dict[str, Type]:
    """Even though get_type_hints claims to follow inheritance, it didn't work on dataclasses."""
    fields = {}

    if isinstance(thing, type):
        local_namespace: Dict[str, Any] = {}

        for kls in reversed(
            thing.__mro__
        ):  # we iterate from least (object()) to most significant base.
            # walk the hierarchy so that we get all of the potential needed imports
            local_namespace.update(vars(sys.modules[kls.__module__]))

        for kls in reversed(thing.__mro__):
            fields.update(get_type_hints(kls, globalns or {}, local_namespace))

        return fields

    assert callable(thing)

    # some builtins (such as object.__init__) have no `__module__` even though they exist in the `builtins` module.
    module = getattr(thing, "__module__", "builtins")
    return get_type_hints(thing, globalns or {}, vars(sys.modules[module]))


def find_return_annotation(method: Callable, globalns: Dict[str, Any] = None) -> Type:
    return find_annotations(method, globalns)["return"]
