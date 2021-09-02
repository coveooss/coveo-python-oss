from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from importlib import import_module
from inspect import isclass
from typing import Tuple, Dict, Any, Type, Sequence

from coveo_functools.annotations import find_annotations
from coveo_functools.flex.types import TypeHint
from coveo_functools.flex.helpers import resolve_hint


@dataclass
class SerializationMetadata:
    module_name: str
    class_name: str
    generics: Sequence[TypeHint] = field(default_factory=list)

    additional_metadata: Dict[str, SerializationMetadata] = field(default_factory=dict)

    @classmethod
    def from_instance(cls, instance: Any) -> SerializationMetadata:
        """Generates serialization metadata out of an instance."""
        if instance is None:
            raise Exception(":travolta-meme:")

        if isclass(instance) or not hasattr(instance, "__class__"):
            raise Exception("Can only reliably serialize from instances.")

        actual_type = instance.__class__

        additional_metadata: Dict[str, SerializationMetadata] = {}

        for argument_name, annotated_type in find_annotations(actual_type).items():
            try:
                # todo: enums probably ain't gonna like this!
                value = getattr(instance, argument_name)
            except AttributeError:
                raise Exception(
                    "Limitation: the argument name must have a matching attribute in the instance."
                )

            if actual_type is not annotated_type:
                # a subclass of the annotation was provided
                additional_metadata[argument_name] = SerializationMetadata.from_instance(value)

        return SerializationMetadata(
            module_name=actual_type.__module__,
            class_name=actual_type.__name__,
            additional_metadata=additional_metadata,
        )

    @classmethod
    def from_annotations(cls, obj: Any) -> SerializationMetadata:
        origin, args = resolve_hint(obj)
        return SerializationMetadata(origin.__module__, origin.__name__, args)

    def import_type(self) -> Type:
        """Import and return the task's class type for deserialization."""
        return getattr(import_module(str(self.module_name)), str(self.class_name))  # type: ignore[no-any-return]

    @cached_property
    def hint(self) -> Any:
        ...



Serialized = Tuple[Dict[str, Any], Dict[str, Any]]


def serialize(obj: Any) -> None:
    if obj is None:
        raise Exception(":travolta-meme:")

    if isclass(obj) or not hasattr(obj, "__class__"):
        raise Exception("Can only reliably serialize from instances.")

    meta = SerializationMetadata.from_instance(obj)
