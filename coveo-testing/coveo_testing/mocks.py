"""
Backward Compatibility Patch: coveo-ref

Before `coveo-ref` was a package, we used it from here.
The current file retains the symbols; there's no practical reason to deprecate anything and cause chaos.

New projects/tests are encouraged to use the `coveo-ref` package directly.
"""

from typing import Any

from coveo_ref.exceptions import (
    RefException,
    UsageError,
    NoQualifiedName,
    CannotImportModule,
    CannotFindSymbol,
    DuplicateSymbol,
)

from coveo_ref import ref

# mark as used:
_ = (
    RefException,
    UsageError,
    NoQualifiedName,
    CannotImportModule,
    CannotFindSymbol,
    DuplicateSymbol,
    ref,
)


def resolve_mock_target(target: Any) -> str:
    """
    Deprecated: You are encouraged to use `ref` instead:

        https://github.com/coveooss/coveo-python-oss/tree/main/coveo-ref

    ---
    Deprecated docs:

    `mock.patch` uses a str-representation of an object to find it, but this doesn't play well with
    refactors and renames. This method extracts the str-representation of an object.

    This method will not handle _all_ kinds of objects, in which case an AttributeError will most likely be raised.
    """
    return f"{target.__module__}.{target.__name__}"
