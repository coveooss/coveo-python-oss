from __future__ import annotations

from typing import Any


JSON_TYPES = (
    bytes,  # technically not a json type, but maximizes compatibility
    str,
    bool,
    int,
    float,
    type(None),
    dict,
)  # list omitted to support list of custom types

PASSTHROUGH_TYPES = {None, Any, *JSON_TYPES}

TypeHint = Any  # :shrug:


def is_passthrough_type(obj: Any) -> bool:
    try:
        return obj in PASSTHROUGH_TYPES
    except TypeError:
        return False
