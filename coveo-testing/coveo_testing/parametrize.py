from collections.abc import Sequence as SequenceType
from typing import Any, Union, Callable, Iterable, cast, Collection, List, Tuple

import pytest


TestArgument = Union[str, List[str], Tuple[str, ...]]  # can also be a comma-separated string
TestIdFormatter = Union[Callable[[Any], str], Collection[str]]
TestFunction = Callable[..., None]


def _parametrized_test_formatter(test_case_value: Any) -> str:
    """ produce a prettier version of a parameter id """
    if isinstance(test_case_value, str):
        pretty = test_case_value
    elif isinstance(test_case_value, SequenceType):
        pretty = "-".join(str(test_case) for test_case in test_case_value)
    else:
        pretty = str(test_case_value)
    return pretty.replace(".", "-")


def parametrize(
    arguments: TestArgument,
    value: Iterable[Any],
    ids: TestIdFormatter = _parametrized_test_formatter,
    **kwargs: Any
) -> TestFunction:
    """ augment the pytest decorator with some id magic (bonus: no more 'pytest.mark.parametrize' typos!) """
    return cast(TestFunction, pytest.mark.parametrize(arguments, value, ids=ids, **kwargs).__call__)
