from dataclasses import dataclass
from typing import Final, Dict, Any, Union

from coveo_functools.flex import FlexFactory
from coveo_testing.markers import UnitTest


@dataclass
class MockLeaf:
    object_id: str


@dataclass
class MockInner:
    object_id: str
    inner: MockLeaf


@dataclass
class MockOuter:
    object_id: str
    inner: MockInner


MOCK_PAYLOAD: Final[Dict[str, Any]] = {
    "object-id": "outer",
    "iNNer": {
        "ObjectId": "inner",
        "inner": {
            "_object__id": "leaf"
        }
    }
}


@UnitTest
def test_flex_factory_detect_and_recurse_objects() -> None:
    instance = FlexFactory(MockOuter)(**MOCK_PAYLOAD)
    assert instance.object_id == 'outer'
    assert instance.inner.object_id == 'inner'
    assert instance.inner.inner.object_id == 'leaf'

    assert isinstance(instance, MockOuter)
    assert isinstance(instance.inner, MockInner)
    assert isinstance(instance.inner.inner, MockLeaf)
