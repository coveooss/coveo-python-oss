from typing import Dict, Type, Callable, Any, Optional, TypeVar


T = TypeVar("T")

_subclass_adapters: Dict[Type, Callable[[Any], Type]] = {}


def register_subclass_adapter(base_class: Type, adapter: Callable[[Any], Type]) -> None:
    """
    Registers a custom callback for a type. This is necessary when an annotation is abstract.

    The callback will receive the raw payload value. It should inspect this payload and return the appropriate type
    for deserialization.
    """
    if base_class in _subclass_adapters:
        raise RuntimeError("An adapter for this class was already registered.")

    _subclass_adapters[base_class] = adapter


def get_subclass_adapter(base_class: Type[T]) -> Optional[Callable[[Any], Type[T]]]:
    return _subclass_adapters.get(base_class)
