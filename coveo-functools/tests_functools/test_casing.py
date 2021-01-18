"""tests the casing tools"""

from coveo_testing.parametrize import parametrize
from coveo_testing.markers import UnitTest

from coveo_functools.casing import snake_case


DUBIOUS_CASINGS = ['TimeOut']


@UnitTest
@parametrize(('test', 'expected'), (
    ('DPMs', 'dpms'),
    ('SearchURI', 'search_uri'),
    ('SearchURIs', 'search_uris'),
    ('CDFNodeProcessA', 'cdf_node_process_a'),
    ('CDFNodeProcess_', 'cdf_node_process_'),
    ('DBs', 'dbs'),
    ('TimeoutA_s', 'timeout_a_s'),
    ('Timeout_ms', 'timeout_ms'),
    ('IDs', 'ids'),
    ('Ids', 'ids'),
    ('_LeadingCHForYOU', '_leading_ch_for_you'),
    ('NumbersNoUnderscore1', 'numbers_no_underscore1'),
    ('TimeOut_s', 'timeout_s'),  # special handling so we don't end up with time_out_s
    ('Jid2Python', 'jid2python')  # special handling so we don't end up with jid2_python
))
def test_snake_case(test: str, expected: str) -> None:
    assert snake_case(test, DUBIOUS_CASINGS) == expected


@UnitTest
def test_bad_casing() -> None:
    # just a sanity check
    fix_casing = ['PoTaTo']
    assert snake_case('PoTaToParty', fix_casing) == 'potato_party'
    assert snake_case('PotaToParty', fix_casing) == 'pota_to_party'
    assert snake_case('PoTaPoTaToParty', fix_casing) == 'po_ta_potato_party'
