from typing import Any


def resolve_mock_target(target: Any) -> str:
    """
    `mock.patch` uses a str-representation of an object to find it, but this doesn't play well with
    refactors and renames. This method extracts the str-representation of an object.

    This method will not handle _all_ kinds of objects, in which case an AttributeError will most likely be raised.
    """
    return f"{target.__module__}.{target.__name__}"
