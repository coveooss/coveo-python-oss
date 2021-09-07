from typing import Dict, Type, Callable, Any, Optional, TypeVar

from coveo_functools.flex.types import TypeHint


T = TypeVar("T")

_subclass_adapters: Dict[Type, Callable[[Any], TypeHint]] = {}


def register_subclass_adapter(hint: TypeHint, adapter: Callable[[Any], TypeHint]) -> None:
    """
    Registers a custom callback for a type. This is necessary when an annotation is abstract.

    The callback will receive the raw payload value. It should inspect this payload and return the appropriate type
    for deserialization.
    """
    if hint in _subclass_adapters:
        raise RuntimeError("An adapter for this class was already registered.")

    _subclass_adapters[hint] = adapter


def get_subclass_adapter(hint: TypeHint) -> Optional[Callable[[Any], Type[T]]]:
    return _subclass_adapters.get(hint)
