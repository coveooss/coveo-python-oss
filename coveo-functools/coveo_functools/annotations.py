"""Annotation-related utilities."""


import sys
from dataclasses import InitVar
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
    _globals = globalns or {}
    _locals = vars(sys.modules[module])

    def __fake_init_var_call(self: Any, *args: Any, **kwargs: Any) -> Any:
        """Technically, there's no `__call__` on instances."""
        return self(*args, **kwargs)

    # fix a python bug with InitVar and forward declarations: https://stackoverflow.com/a/70430449
    for namespace in _globals, _locals:
        if (
            init_var_class := namespace.get("InitVar")
        ) is InitVar and init_var_class.__call__ is not __fake_init_var_call:
            init_var_class.__call__ = __fake_init_var_call

    return get_type_hints(thing, _globals, _locals)


def find_return_annotation(method: Callable, globalns: Dict[str, Any] = None) -> Type:
    return find_annotations(method, globalns)["return"]
