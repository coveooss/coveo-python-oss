from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Type, Any

import pytest
from coveo_functools.exceptions import UnsupportedAnnotation
from coveo_functools.flex import deserialize
from coveo_functools.flex.subclass_adapter import register_subclass_adapter, _subclass_adapters
from coveo_testing.parametrize import parametrize


@pytest.fixture(autouse=True)
def _clear_adapters_between_tests() -> None:
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


@parametrize("implementation_class", (
    Implementation,
    DataclassImplementation
))
def test_deserialize_adapter(implementation_class: Type) -> None:
    def adapter(value: Any) -> Type:
        return implementation_class

    register_subclass_adapter(Abstract, adapter)
    parent = deserialize({"test": {}}, hint=Parent)
    assert isinstance(parent.test, implementation_class)
