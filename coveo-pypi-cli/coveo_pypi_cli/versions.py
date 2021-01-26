"""version-related helpers"""

from distutils.version import StrictVersion, Version
from typing import Union, Optional


class StrictVersionHelper(StrictVersion):
    """internal helper 'coz tuple juggling is no fun!"""

    def __init__(self, vstring: Union[Version, str] = None) -> None:
        super().__init__(str(vstring) if vstring else None)

    @property
    def major(self) -> int:
        return self.version[0]

    @major.setter
    def major(self, value: int) -> None:
        self.version = (value, self.minor, self.patch)

    @property
    def minor(self) -> int:
        return self.version[1]

    @minor.setter
    def minor(self, value: int) -> None:
        self.version = (self.major, value, self.patch)

    @property
    def patch(self) -> int:
        return self.version[2]

    @patch.setter
    def patch(self, value: int) -> None:
        self.version = (self.major, self.minor, value)

    @property
    def prerelease_stage(self) -> Optional[str]:
        return self.prerelease[0] if self.prerelease else None

    @prerelease_stage.setter
    def prerelease_stage(self, value: Optional[str]) -> None:
        self.prerelease = None if value is None else (value, self.prerelease_num)

    @property
    def prerelease_num(self) -> Optional[int]:
        return self.prerelease[1] if self.prerelease else None

    @prerelease_num.setter
    def prerelease_num(self, value: Optional[int]) -> None:
        self.prerelease = None if value is None else (self.prerelease_stage, value)

    def bump_next_release(self) -> None:
        """Bumps the current version to the next release."""
        if not self.prerelease:
            # 1.4.4 bumps to 1.4.5
            self.patch += 1
        else:
            ...  # nothing do to: 1.4.5a3 would become 1.4.5

        self.prerelease = None

    def bump_next_prerelease(self, *, patch: bool = True) -> None:
        """Bumps the current version to the next prerelease."""
        if self.prerelease:
            # 1.4.5a4 bumps to 1.4.5a5
            self.prerelease_num += 1
        else:
            # 1.4.4 bumps to 1.4.5a1
            self.patch += int(patch)  # either 1 or 0
            self.prerelease = ("a", 1)

    def __copy__(self) -> "StrictVersionHelper":
        return StrictVersionHelper(self)
