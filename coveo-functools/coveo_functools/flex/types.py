from __future__ import annotations

from typing import Any


JSON_TYPES = (
    str,
    bool,
    int,
    float,
    type(None),
    dict,
)  # list omitted to support list of custom types

PASSTHROUGH_TYPES = {None, Any, *JSON_TYPES}


TypeHint = Any  # :shrug:
