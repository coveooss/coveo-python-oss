from typing import TypeVar, Any, Dict, Optional, Iterator, Union, Type

from coveo_functools.casing import flexfactory

from coveo_pyproject.ci.mypy_runner import MypyRunner
from coveo_pyproject.ci.poetry_runners import PoetryCheckRunner
from coveo_pyproject.ci.pyproject_runners import CheckOutdatedRunner, OfflineInstallRunner
from coveo_pyproject.ci.pytest_runner import PytestRunner
from coveo_pyproject.ci.runner import ContinuousIntegrationRunner
from coveo_pyproject.metadata.pyproject_api import PythonProjectAPI

T = TypeVar("T")

CIConfig = Optional[Union[Dict[str, Any], bool]]


class ContinuousIntegrationConfig:
    def __init__(
        self,
        *,
        disabled: bool = False,
        mypy: CIConfig = True,
        check_outdated: CIConfig = True,
        pytest: CIConfig = True,
        poetry_check: CIConfig = True,
        offline_build: CIConfig = True,
        _pyproject: PythonProjectAPI
    ):
        self._pyproject = _pyproject
        self.disabled = disabled  # a master switch used by pyproject to skip this project.
        self.mypy: Optional[MypyRunner] = self._flexfactory(MypyRunner, mypy)
        self.mypy = None  # disabled until mypy>=0.800; see IDXINFRA-590
        self.check_outdated: Optional[CheckOutdatedRunner] = self._flexfactory(
            CheckOutdatedRunner, check_outdated
        )
        self.pytest: Optional[PytestRunner] = self._flexfactory(PytestRunner, pytest)
        self.poetry_check: Optional[PoetryCheckRunner] = self._flexfactory(
            PoetryCheckRunner, poetry_check
        )
        self.offline_build: Optional[OfflineInstallRunner] = self._flexfactory(
            OfflineInstallRunner, offline_build
        )

    def _flexfactory(self, cls: Type[T], config: Optional[CIConfig]) -> Optional[T]:
        """handles the true form of the config. like mypy = true """
        if config in (None, False):
            return None
        if config is True:
            config = {}
        return flexfactory(cls, **config, _pyproject=self._pyproject)  # type: ignore

    @property
    def runners(self) -> Iterator[ContinuousIntegrationRunner]:
        return filter(
            lambda runner: isinstance(runner, ContinuousIntegrationRunner), self.__dict__.values()
        )
