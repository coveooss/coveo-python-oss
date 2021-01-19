""" Test SetLoggingLevel. """

import logging

from coveo_testing.logging import SetLoggingLevel
from coveo_testing.markers import UnitTest

log = logging.getLogger(__name__)


@UnitTest
def test_set_logging_level() -> None:
    """ Test SetLoggingLevel. """
    level = log.getEffectiveLevel()
    with SetLoggingLevel(__name__, level + 1):
        assert log.getEffectiveLevel() == level + 1
    assert log.getEffectiveLevel() == level
