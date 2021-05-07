from typing import Optional, Sequence


class InSequence:
    def __init__(self, *args: str, condition: Optional[Sequence[str]] = None) -> None:
        if condition is None:
            self._condition = tuple(args)
        else:
            self._condition = tuple(condition)

    def __call__(self, value: str) -> Optional[str]:
        if value not in self._condition:
            values = ", ".join(self._condition)
            return f"Valid values are : {values}"
        return None
