from enum import Enum, auto
from typing import Iterable, Tuple, Union, List

from coveo_stew.ci.runner import ContinuousIntegrationRunner, RunnerStatus
from coveo_stew.environment import PythonEnvironment
from coveo_stew.exceptions import CannotLoadProject
from coveo_stew.metadata.pyproject_api import PythonProjectAPI
from coveo_systools.filesystem import find_repo_root
from coveo_systools.subprocess import check_output


class WorkingDirectoryKind(Enum):
    Project = auto()
    Repository = auto()

    @classmethod
    def valid_values(cls) -> Tuple[str, ...]:
        return tuple(kind.name for kind in cls)


class AnyRunner(ContinuousIntegrationRunner):
    """Custom runners"""

    def __init__(
        self,
        *,
        name: str,
        args: Union[str, List[str]] = "",
        check_failed_exit_codes: Iterable[int] = (1,),
        create_generic_report: bool = False,
        working_directory: str = "project",
        _pyproject: PythonProjectAPI,
    ) -> None:
        super().__init__(_pyproject=_pyproject)
        self._name = name
        self.args = args or []
        self.check_failed_exit_codes = check_failed_exit_codes
        self.outputs_own_report = not create_generic_report

        try:
            self.working_directory = WorkingDirectoryKind[working_directory.title()]
        except KeyError:
            raise CannotLoadProject(
                f"Working directory for {self.name} should be within {WorkingDirectoryKind.valid_values}"
            )

    def _launch(self, environment: PythonEnvironment, *extra_args: str) -> RunnerStatus:
        args = [self.args] if isinstance(self.args, str) else self.args
        command = environment.build_command(self.name, *args)

        working_directory = self._pyproject.project_path
        if self.working_directory is WorkingDirectoryKind.Repository:
            working_directory = find_repo_root(working_directory)

        check_output(
            *command,
            *extra_args,
            working_directory=working_directory,
            verbose=self._pyproject.verbose,
        )

        return RunnerStatus.Success

    @property
    def name(self) -> str:
        return self._name
