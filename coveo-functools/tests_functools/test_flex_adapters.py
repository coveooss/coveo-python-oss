from __future__ import annotations

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Type, Any, Generator, List, Dict, Optional, cast

import pytest
from coveo_functools.exceptions import UnsupportedAnnotation
from coveo_functools.flex import deserialize, TypeHint
from coveo_functools.flex.factory_adapter import register_factory_adapter
from coveo_functools.flex.serializer import SerializationMetadata
from coveo_functools.flex.subclass_adapter import register_subclass_adapter, _subclass_adapters
from coveo_testing.parametrize import parametrize


@pytest.fixture(autouse=True)
def _clear_adapters_between_tests() -> Generator[None, None, None]:
    try:
        yield
    finally:
        _subclass_adapters.clear()


class Abstract(metaclass=ABCMeta):
    @abstractmethod
    def api(self) -> None:
        ...


@dataclass
class Implementation(Abstract):
    value: Optional[str] = None

    def api(self) -> None:
        ...


@dataclass
class DataclassImplementation(Abstract):
    def api(self) -> None:
        ...


@dataclass
class Parent:
    test: Abstract


def test_flex_raise_on_abstract() -> None:
    with pytest.raises(UnsupportedAnnotation):
        deserialize({}, hint=Abstract)


@parametrize("implementation_class", (Implementation, DataclassImplementation))
def test_deserialize_adapter(implementation_class: Type) -> None:
    def adapter(value: Any) -> Type:
        return implementation_class

    register_subclass_adapter(Abstract, adapter)
    parent = deserialize({"test": {}}, hint=Parent)
    assert isinstance(parent.test, implementation_class)


def test_deserialize_adapter_nested() -> None:
    def adapter(value: Any) -> Type:
        return Implementation

    @dataclass
    class Nested:
        nested: Parent

    register_subclass_adapter(Abstract, adapter)
    instance = deserialize({"nested": {"test": {}}}, hint=Nested)
    assert isinstance(instance.nested.test, Implementation)


def test_deserialize_funky_adapter() -> None:
    """The adapter is allowed to provide any substitute."""

    def adapter(value: Any) -> Type:
        return List[str]

    register_subclass_adapter(Abstract, adapter)
    assert deserialize({"test": ["a", "b", "c"]}, hint=Parent).test == ["a", "b", "c"]


def test_deserialize_any_adapter() -> None:
    """Even Any, which could be very powerful."""

    def any_adapter(value: Any) -> TypeHint:
        if isinstance(value, list):
            return List[Abstract]
        if isinstance(value, dict):
            return Dict[str, Abstract]
        return Any

    def abstract_adapter(value: Any) -> TypeHint:
        return Implementation

    register_subclass_adapter(Any, any_adapter)
    register_subclass_adapter(Abstract, abstract_adapter)

    instance: Any = deserialize([{}, {}, {}], hint=Any)
    assert (
        isinstance(instance, list)
        and instance
        and all(isinstance(item, Implementation) for item in instance)
    )

    instance = deserialize({"item1": {}, "item2": {}}, hint=Any)
    assert isinstance(instance, dict) and instance
    assert isinstance(instance["item1"], Implementation)
    assert isinstance(instance["item2"], Implementation)


def test_deserialize_mutate_value_adapter() -> None:
    """The adapter can mutate the payload."""

    def payload_adapter(value: Any) -> TypeHint:
        assert isinstance(value, dict)
        if "test" not in value:
            value["test"] = {"value": "success"}
        return Parent

    def abstract_adapter(value: Any) -> TypeHint:
        return Implementation

    register_subclass_adapter(Parent, payload_adapter)
    register_subclass_adapter(Abstract, abstract_adapter)

    # the payload will be mutated
    payload: Dict[str, Any] = {}
    instance = deserialize(payload, hint=Parent)
    assert "test" in payload
    assert isinstance(instance.test, Implementation)
    assert instance.test.value == "success"


@dataclass
class TestFactory:
    value: str

    @classmethod
    def factory(cls, raw: Dict[str, str]) -> TestFactory:
        return deserialize(raw, hint=TestFactory)


def test_deserialize_adapter_factory_classmethod() -> None:
    """The adapter may return a callable."""

    def factory_adapter(value: Any) -> TypeHint:
        return TestFactory.factory if "raw" in value else TestFactory

    register_subclass_adapter(TestFactory, factory_adapter)

    payload: Dict[str, Any] = {"raw": {"value": "success"}}
    assert deserialize(payload, hint=TestFactory).value == "success"


@dataclass
class TestDatetimeFactory:
    value: datetime


def datetime_factory(value: str) -> datetime:
    return datetime.fromisoformat(value)


register_factory_adapter(datetime, datetime_factory)


def test_deserialize_adapter_factory_function() -> None:
    """Tests the factory feature, which expects the instance to be returned instead of the type."""
    test_datetime = datetime.utcnow()
    payload: Dict[str, Any] = {"value": test_datetime.isoformat()}
    assert deserialize(payload, hint=TestDatetimeFactory).value == test_datetime


def test_deserialize_with_meta_and_factory() -> None:
    """Tests a bug where using the metadata bypassed the factory adapters."""
    timestamp = datetime.utcnow()
    instance = TestDatetimeFactory(value=timestamp)
    meta = SerializationMetadata.from_instance(instance)
    deserialized = cast(
        TestDatetimeFactory, deserialize({"value": timestamp.isoformat()}, hint=meta)
    )
    assert deserialized.value == timestamp
