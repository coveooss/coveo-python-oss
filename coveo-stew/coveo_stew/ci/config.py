from typing import TypeVar, Any, Dict, Optional, Iterator, Union, Type

from coveo_functools.casing import flexfactory
from coveo_stew.ci.any_runner import AnyRunner

from coveo_stew.ci.black_runner import BlackRunner
from coveo_stew.ci.mypy_runner import MypyRunner
from coveo_stew.ci.poetry_runners import PoetryCheckRunner
from coveo_stew.ci.stew_runners import CheckOutdatedRunner, OfflineInstallRunner
from coveo_stew.ci.pytest_runner import PytestRunner
from coveo_stew.ci.runner import ContinuousIntegrationRunner
from coveo_stew.exceptions import CannotLoadProject
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
        custom_runners: Optional[Dict[str, CIConfig]] = None,
        _pyproject: PythonProjectAPI,
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

        # custom runners are entirely dynamic
        for runner_name, runner_config in (custom_runners or {}).items():
            if hasattr(self, runner_name):
                raise CannotLoadProject(
                    f"Custom runner {runner_name} conflicts with the builtin version."
                )
            setattr(
                self, runner_name, self._flexfactory(AnyRunner, runner_config, name=runner_name)
            )

    def _flexfactory(self, cls: Type[T], config: Optional[CIConfig], **extra: str) -> Optional[T]:
        """handles the true form of the config. like mypy = true"""
        if config in (None, False):
            return None
        if config is True:
            config = {}
        return flexfactory(cls, **config, **extra, _pyproject=self._pyproject)  # type: ignore

    @property
    def runners(self) -> Iterator[ContinuousIntegrationRunner]:
        runners = filter(
            lambda runner: isinstance(runner, ContinuousIntegrationRunner), self.__dict__.values()
        )
        # if e.g. mypy finds errors and then black fixes the file, the line numbers from mypy may no longer
        # be valid.
        yield from sorted(runners, key=lambda runner: 0 if runner.supports_auto_fix else 1)
