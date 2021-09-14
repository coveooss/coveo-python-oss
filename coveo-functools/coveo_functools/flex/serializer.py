from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from inspect import isclass
from typing import Any, Dict

from coveo_functools.annotations import find_annotations
from coveo_functools.flex.types import TypeHint


@dataclass
class SerializationMetadata:
    module_name: str
    class_name: str
    additional_metadata: Dict[str, SerializationMetadata] = field(default_factory=dict)

    @classmethod
    def from_instance(cls, instance: Any) -> SerializationMetadata:
        """Generates serialization metadata out of an instance."""
        if instance is None:
            raise Exception(":travolta-meme:")

        if isclass(instance) or not hasattr(instance, "__class__"):
            raise Exception("Can only reliably serialize from instances.")

        actual_type = instance.__class__
        additional_metadata: Dict[Any, SerializationMetadata] = {}

        if isinstance(instance, list):
            # the additional metadata will be a map of the index to that object's metadata.
            # we use strings to accommodate json, which cannot have ints as keys.
            additional_metadata = {
                str(idx): SerializationMetadata.from_instance(obj)
                for idx, obj in enumerate(instance)
            }
        elif isinstance(instance, dict):
            # the additional metadata maps arguments to their actual type
            additional_metadata = {
                key: SerializationMetadata.from_instance(obj)
                for key, obj in instance.items()
                if obj is not None
            }
        else:
            # custom objects; start from the static annotations...
            for argument_name, annotated_type in find_annotations(actual_type).items():
                try:
                    value = getattr(instance, argument_name)
                except AttributeError:
                    raise Exception(
                        "Limitation: the argument name must have a matching attribute in the instance."
                    )

                # save this meta / recurse
                additional_metadata[argument_name] = SerializationMetadata.from_instance(value)

        return SerializationMetadata(
            module_name=actual_type.__module__,
            class_name=actual_type.__name__,
            additional_metadata=additional_metadata,
        )

    def import_type(self) -> TypeHint:
        """Import and return the task's class type for deserialization."""
        return getattr(import_module(str(self.module_name)), str(self.class_name))
