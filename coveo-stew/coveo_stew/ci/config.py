from typing import TypeVar, Any, Dict, Optional, Iterator, Union, Type

from coveo_functools.casing import flexfactory
from coveo_stew.ci.black_runner import BlackRunner

from coveo_stew.ci.mypy_runner import MypyRunner
from coveo_stew.ci.poetry_runners import PoetryCheckRunner
from coveo_stew.ci.stew_runners import CheckOutdatedRunner, OfflineInstallRunner
from coveo_stew.ci.pytest_runner import PytestRunner
from coveo_stew.ci.runner import ContinuousIntegrationRunner
from coveo_stew.metadata.pyproject_api import PythonProjectAPI

T = TypeVar("T")

CIConfig = Optional[Union[Dict[str, Any], bool]]


class ContinuousIntegrationConfig:
    def __init__(
        self,
        *,
        disabled: bool = False,
        mypy: CIConfig = True,
        check_outdated: CIConfig = True,
        poetry_check: CIConfig = True,
        pytest: CIConfig = False,
        offline_build: CIConfig = False,
        black: CIConfig = False,
        _pyproject: PythonProjectAPI
    ):
        self._pyproject = _pyproject
        self.disabled = disabled  # a master switch used by stew to skip this project.
        self.mypy: Optional[MypyRunner] = self._flexfactory(MypyRunner, mypy)
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
        self.black: Optional[BlackRunner] = self._flexfactory(BlackRunner, black)

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
