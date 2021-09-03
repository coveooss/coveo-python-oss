from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Type, Any, Generator, List, Dict

import pytest
from coveo_functools.exceptions import UnsupportedAnnotation
from coveo_functools.flex import deserialize
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


class Implementation(Abstract):
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
    def any_adapter(value: Any) -> Type:
        if isinstance(value, list):
            return List[Abstract]
        if isinstance(value, dict):
            return Dict[str, Abstract]
        return Any

    def abstract_adapter(value: Any) -> Type:
        return Implementation

    register_subclass_adapter(Any, any_adapter)
    register_subclass_adapter(Abstract, abstract_adapter)

    instance: Any = deserialize([{}, {}, {}], hint=Any)
    assert isinstance(instance, list) and instance and all(isinstance(item, Implementation) for item in instance)

    instance = deserialize({"item1": {}, "item2": {}}, hint=Any)
    assert isinstance(instance, dict) and instance
    assert isinstance(instance['item1'], Implementation)
    assert isinstance(instance['item2'], Implementation)
