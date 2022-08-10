import math
import time

from unittest.mock import Mock, patch

from coveo_testing.noyield import no_yield


@patch('math.sqrt', return_value="mock1")
@no_yield(patch("math.floor", return_value="mock2"))
@patch('time.time', return_value='mock3')
def test_it(mock3: Mock, mock1: Mock) -> None:
    assert mock1() == math.sqrt(1) == "mock1"
    assert mock3() == time.time() == "mock3"
    assert math.floor(1.0) == "mock2"
