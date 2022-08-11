from typing import Callable, List, Any, Generator

import pytest
from _pytest.fixtures import SubRequest
from _pytest.mark import MarkDecorator


def use_fixtures(*fixtures: Callable) -> MarkDecorator:
    """Shorter and refactorable version of "@pytest.mark.usefixtures"."""
    return pytest.mark.use_fixtures(fixture.__name__ for fixture in fixtures)


def enable_fixtures(request: SubRequest, *fixtures: Callable) -> List[Any]:
    """Enable fixtures from code and return the values in order."""

    def _() -> Generator[Any, None, None]:
        for fixture in fixtures:
            yield request.getfixturevalue(fixture.__name__)

    return list(_())
