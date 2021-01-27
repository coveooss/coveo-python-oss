from typing import Dict, Any

from coveo_systools.subprocess import check_output, DetailedCalledProcessError

from coveo_pyproject.ci.runner import ContinuousIntegrationRunner, RunnerStatus
from coveo_pyproject.environment import (
    PythonEnvironment,
    PythonTool,
    coveo_pyproject_environment,
)


class BlackRunner(ContinuousIntegrationRunner):
    name: str = "black"
    check_failed_exit_codes = [1]

    def _launch(self, environment: PythonEnvironment, *extra_args: str) -> RunnerStatus:
        try:
            self._launch_internal(environment, "--check", "--quiet", *extra_args)
        except DetailedCalledProcessError:
            # re-run without the quiet switch so that the output appears in the console
            self._launch_internal(environment, "--check", *extra_args)
        return RunnerStatus.Success

    def auto_fix(self, environment: PythonEnvironment) -> None:
        self._launch_internal(environment, "--quiet")

    def _launch_internal(self, environment: PythonEnvironment, *extra_args: str) -> None:
        # projects may opt to use coveo-pyproject's black version by not including black in their dependencies.
        black_environment = (
            environment if environment.black_executable.exists() else coveo_pyproject_environment
        )
        command = black_environment.build_command(PythonTool.Black, ".", *extra_args)
        check_output(
            *command,
            working_directory=self._pyproject.project_path,
            verbose=self._pyproject.verbose
        )
