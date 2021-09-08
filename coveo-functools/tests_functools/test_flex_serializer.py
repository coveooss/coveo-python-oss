from __future__ import annotations

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, asdict
from typing import List, Type, Any, Dict, Union, Optional

from coveo_functools.flex import deserialize, TypeHint
from coveo_functools.flex.serializer import SerializationMetadata
from coveo_testing.parametrize import parametrize


class AbstractClass(metaclass=ABCMeta):
    @abstractmethod
    def api(self) -> None:
        ...


@dataclass
class MockSubClass(AbstractClass):
    value: str

    def api(self) -> None:
        ...


@dataclass
class MockRootClass:
    extra: AbstractClass


def test_serialization_metadata() -> None:
    subclass = MockSubClass("test")
    root = MockRootClass(subclass)
    meta = SerializationMetadata.from_instance(root)
    serialized = asdict(root)

    deserialize(serialized, hint=meta)


def test_serialization_metadata_from_annotations() -> None:
    meta = SerializationMetadata.from_annotations(MockSubClass)
    assert meta.import_type() is MockSubClass


@parametrize(
    ("hint", "expected_type", "expected_generics"),
    (
        (List[str], list, [str]),
        (List[Union[str, int]], list, [Union[str, int]]),
        (Dict[str, Any], dict, [str, Any]),
        (Union[List[str], str], Union, [str, List[str]]),
        (Optional[str], Union, [str]),
    ),
)
def test_serialization_metadata_from_annotations2(
    hint: TypeHint, expected_type: Type, expected_generics: List[Type]
) -> None:
    meta = SerializationMetadata.from_annotations(hint)
    assert meta.import_type() is expected_type
    assert meta.generics and expected_generics
    assert set(meta.generics) == set(expected_generics)
