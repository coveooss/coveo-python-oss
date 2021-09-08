from __future__ import annotations

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto

import pytest
from coveo_functools.flex import deserialize
from coveo_functools.flex.serializer import SerializationMetadata


class AbstractClass(metaclass=ABCMeta):
    @abstractmethod
    def api(self) -> None:
        ...


class MockEnum(Enum):
    Default = auto()
    Value = auto()


@dataclass
class MockSubClass(AbstractClass):
    value: str
    enum_test: MockEnum = MockEnum.Default

    def api(self) -> None:
        ...


@dataclass
class MockWithAbstract:
    extra: AbstractClass


@dataclass
class MockWithNested:
    root: MockWithAbstract


def test_serialization_metadata() -> None:
    meta = SerializationMetadata.from_instance(MockWithAbstract(MockSubClass("test")))
    assert deserialize({"extra": {"value": "test"}}, hint=meta).extra.value == "test"  # type: ignore[attr-defined]

    # it cannot work without the meta because of the abstract class
    with pytest.raises(Exception):
        deserialize({"extra": {"value": "test"}}, hint=MockWithAbstract)


def test_serialization_recursive() -> None:
    """This ensures that we correctly catch the implementation of nested abstract annotations."""

    payload = {"root": {"extra": {"value": "test"}}}

    # we can create annotations metadata from abstract classes, because an adapter could handle it later
    meta = SerializationMetadata.from_annotations(MockWithNested)

    with pytest.raises(Exception):
        # without an adapter, you cannot deserialize the payload using that meta information because of the abstract.
        deserialize(payload, hint=meta)

    # from an instance, the implementation is detected and then restored.
    meta = SerializationMetadata.from_instance(
        MockWithNested(MockWithAbstract(MockSubClass("test")))
    )
    assert deserialize(payload, hint=meta).root.extra.value == "test"  # type: ignore[attr-defined]


def test_serialization_enum() -> None:
    """Enums require some more code, so here we go."""
    instance = MockSubClass("test", MockEnum.Value)
    meta = SerializationMetadata.from_instance(instance)
    payload = {"value": "test", "enum_test": "Value"}
    assert deserialize(payload, hint=meta).enum_test is MockEnum.Value  # type: ignore[attr-defined]
