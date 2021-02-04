from pathlib import Path
import pkg_resources
import re
from typing import Generator

from coveo_styles.styles import echo
from coveo_systools.filesystem import find_paths
from coveo_systools.subprocess import check_output

from coveo_stew.ci.runner import ContinuousIntegrationRunner, RunnerStatus
from coveo_stew.environment import PythonEnvironment, PythonTool, coveo_stew_environment
from coveo_stew.metadata.python_api import PythonFile


class MypyRunner(ContinuousIntegrationRunner):
    name: str = "mypy"
    check_failed_exit_codes = [1]
    outputs_own_report = True

    def _mypy_config_path(self) -> Path:
        """Returns the path to the mypy config file."""
        try:
            return next(
                find_paths(
                    Path("mypy.ini"),
                    self._pyproject.project_path,
                    in_root=True,
                    in_parents=True,
                    in_children=True,
                )
            )
        except StopIteration:
            # none can be found; using our own opinionated version.
            return Path(pkg_resources.resource_filename("coveo_stew", "package_resources/mypy.ini"))

    def _find_typed_folders(self) -> Generator[Path, None, None]:
        """Yield the folders of this project that should be type-checked."""
        yield from filter(
            lambda path: (path / PythonFile.TypedPackage).exists(),
            self._pyproject.project_path.iterdir(),
        )

    def _launch(self, environment: PythonEnvironment, *extra_args: str) -> RunnerStatus:
        typed_folders = tuple(folder.name for folder in self._find_typed_folders())

        if not typed_folders:
            self._last_output = [
                "Cannot find a py.typed file: https://www.python.org/dev/peps/pep-0561/"
            ]
            return RunnerStatus.Error

        # mypy needs the dependencies installed in an environment in order to inspect them.
        self._pyproject.install(quiet=True)

        # projects may opt to use coveo-stew's mypy version by not including mypy in their dependencies.
        mypy_environment = (
            environment if environment.mypy_executable.exists() else coveo_stew_environment
        )

        command = mypy_environment.build_command(
            PythonTool.Mypy,
            # the --python-executable switch tells mypy in which environment the imports should be followed.
            "--python-executable",
            environment.python_executable,
            "--config-file",
            self._mypy_config_path(),
            "--cache-dir",
            self._pyproject.project_path / ".mypy_cache",
            "--show-error-codes",
            f"--junit-xml={self.report_path(environment)}",
            *extra_args,  # any extra argument provided by the caller
            *typed_folders,  # what to lint
        )

        if self._pyproject.verbose:
            echo.normal(command)

        check_output(
            *command,
            working_directory=self._pyproject.project_path,
            verbose=self._pyproject.verbose,
        )
        return RunnerStatus.Success

    def echo_last_failures(self) -> None:
        if not self._last_output:
            return

        pattern = re.compile(
            rf"^(?P<path>.+\.py):(?P<line>\d+):(?P<column>\d+(?::)| )"
            rf"(?:\s?error:\s?)(?P<detail>.+)$"
        )

        for line in self._last_output:
            match = pattern.fullmatch(line)
            if match:
                adjusted_path = (self._pyproject.project_path / Path(match["path"])).resolve()
                echo.error_details(
                    f'{adjusted_path}:{match["line"]}:{match["column"]} {match["detail"]}'
                )
            else:
                echo.noise(line)
