from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from inspect import isclass
from typing import Any, get_origin, Dict

from coveo_functools.annotations import find_annotations
from coveo_functools.exceptions import UnsupportedAnnotation
from coveo_functools.flex.helpers import resolve_hint
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

        additional_metadata: Dict[str, SerializationMetadata] = {}

        if isinstance(instance, list):
            additional_metadata = {
                str(idx): SerializationMetadata.from_instance(obj)
                for idx, obj in enumerate(instance)
            }
        elif isinstance(instance, dict):
            additional_metadata = {
                key: SerializationMetadata.from_instance(obj) for key, obj in instance.items()
            }
        else:
            for argument_name, annotated_type in find_annotations(actual_type).items():
                try:
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

        for key in "__name__", "_name":
            if origin_name := getattr(origin, key, None):
                break
        else:
            raise UnsupportedAnnotation(origin)

        # if get_origin finds something, we have a generic in hands and the "args" will contain the generics.
        additional_metadata: Dict[str, SerializationMetadata] = (
            {}
            if get_origin(obj) is not None
            else {
                argument_name: SerializationMetadata.from_annotations(annotation)
                for argument_name, annotation in find_annotations(obj).items()
            }
        )

        return SerializationMetadata(
            origin.__module__, origin_name, additional_metadata=additional_metadata
        )

    def import_type(self) -> TypeHint:
        """Import and return the task's class type for deserialization."""
        return getattr(import_module(str(self.module_name)), str(self.class_name))
