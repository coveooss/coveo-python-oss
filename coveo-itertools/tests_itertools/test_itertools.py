"""test our itertool helper"""

import pytest
from coveo_testing.markers import UnitTest

from coveo_itertools.lookups import dict_lookup


@UnitTest
def test_dict_lookup() -> None:
    example = {'nested': {'key': {'lookup': True}}}
    assert dict_lookup(example, 'nested', 'key', 'lookup') is True
    with pytest.raises(KeyError):
        dict_lookup(example, 'nested', 'key', 'failure')
    assert dict_lookup(example, 'nested', 'key', 'failure', default=[]) == []
