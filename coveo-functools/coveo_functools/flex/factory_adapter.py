from typing import Dict, Type, Callable, Any, Optional, TypeVar

from coveo_functools.flex.types import TypeHint


T = TypeVar("T")

_factory_adapters: Dict[Type, Callable[[Any], TypeHint]] = {}


def register_factory_adapter(hint: TypeHint, factory: Callable[[Any], T]) -> None:
    """
    Registers a custom factory for a type.

    The factory will receive the raw payload value. It should return an instance of the proper type.
    """
    if hint in _factory_adapters:
        raise RuntimeError("A factory for this class was already registered.")

    _factory_adapters[hint] = factory


def get_factory_adapter(hint: TypeHint) -> Optional[Callable[[Any], T]]:
    try:
        hash(hint)
    except TypeError:
        return None

    return _factory_adapters.get(hint)
