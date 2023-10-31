from __future__ import annotations

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, asdict
from enum import Enum, auto
from typing import List, Dict, Optional

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
class MockSubClass2(AbstractClass):
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


@dataclass
class MockOptionalList:
    value: Optional[List[Optional[int]]]


def test_serialization_metadata() -> None:
    meta = SerializationMetadata.from_instance(MockWithAbstract(MockSubClass("test")))
    assert deserialize({"extra": {"value": "test"}}, hint=meta, errors="raise").extra.value == "test"  # type: ignore[attr-defined]

    # it cannot work without the meta because of the abstract class
    with pytest.raises(Exception):
        deserialize({"extra": {"value": "test"}}, hint=MockWithAbstract, errors="raise")


def test_serialization_recursive() -> None:
    """This ensures that we correctly catch the implementation of nested abstract annotations."""

    payload = {"root": {"extra": {"value": "test"}}}

    # from an instance, the implementation is detected and then restored.
    meta = SerializationMetadata.from_instance(
        MockWithNested(MockWithAbstract(MockSubClass("test")))
    )
    assert deserialize(payload, hint=meta, errors="raise").root.extra.value == "test"  # type: ignore[attr-defined]


def test_serialization_enum() -> None:
    """Enums require some more code, so here we go."""
    instance = MockSubClass("test", MockEnum.Value)
    meta = SerializationMetadata.from_instance(instance)
    payload = {"value": "test", "enum_test": "Value"}
    assert deserialize(payload, hint=meta, errors="raise").enum_test is MockEnum.Value  # type: ignore[attr-defined]


def test_serialization_abstract_in_list() -> None:
    lst = [MockSubClass("first"), MockSubClass2("second")]
    meta = SerializationMetadata.from_instance(lst)

    with pytest.raises(Exception):
        deserialize(
            [{"value": "first"}, {"value": "second"}], hint=List[AbstractClass], errors="raise"
        )

    result = deserialize([{"value": "first"}, {"value": "second"}], hint=meta, errors="raise")
    assert result[0].value == "first" and result[1].value == "second"  # type: ignore[index]
    assert isinstance(result[0], MockSubClass)  # type: ignore[index]
    assert isinstance(result[1], MockSubClass2)  # type: ignore[index]


def test_serialization_abstract_in_dict() -> None:
    payload = {"first": {"value": "first"}, "second": {"value": "second"}}
    dct = {"first": MockSubClass("first"), "second": MockSubClass2("second")}

    meta = SerializationMetadata.from_instance(dct)

    with pytest.raises(Exception):
        deserialize(payload, hint=Dict[str, AbstractClass], errors="raise")

    result = deserialize(
        {"first": {"value": "first"}, "second": {"value": "second"}}, hint=meta, errors="raise"
    )
    assert result["first"].value == "first" and result["second"].value == "second"  # type: ignore[index]
    assert isinstance(result["first"], MockSubClass)  # type: ignore[index]
    assert isinstance(result["second"], MockSubClass2)  # type: ignore[index]


def test_serialization_none_in_list() -> None:
    lst = MockOptionalList([1, 2, None, 4])
    meta = SerializationMetadata.from_instance(lst)
    result = deserialize({"value": [1, 2, None, 4]}, hint=meta, errors="raise")
    assert result.value == [1, 2, None, 4]  # type: ignore[attr-defined]


def test_serialization_none_in_custom_object() -> None:
    obj = MockOptionalList(None)
    meta = SerializationMetadata.from_instance(obj)
    result = deserialize({"value": None}, hint=meta, errors="raise")
    assert result.value is None  # type: ignore[attr-defined]


def test_serialization_can_serialize_serialization_metadata() -> None:
    """There was an issue where you couldn't serialize/deserialize the SerializationMetadata class."""
    instance = SerializationMetadata("patate", "poire")
    meta = SerializationMetadata.from_instance(instance)
    payload = asdict(instance)
    assert deserialize(payload, hint=SerializationMetadata, errors="raise").module_name == "patate"
    assert deserialize(payload, hint=meta, errors="raise").module_name == "patate"
