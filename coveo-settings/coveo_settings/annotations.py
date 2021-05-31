from pathlib import Path
from typing import Union, Dict, TypeVar, Callable, Iterable


ConfigValue = Union[str, int, float, bool, dict, Path]
ConfigDict = Dict[str, ConfigValue]

T = TypeVar("T", str, int, float, bool, dict, Path)
ValidationCallback = Callable[[T], str]
Validation = Union[ValidationCallback, Iterable[T]]
