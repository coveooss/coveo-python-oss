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
        # projects may opt to use coveo-pyproject's black version by not including black in their dependencies.
        black_environment = environment if environment.black_executable.exists() else coveo_pyproject_environment

        command = black_environment.build_command(
            PythonTool.Black, ".", "--check", *extra_args  # scan all python files in the project folder; includes tests
        )

        kwargs: Dict[str, Any] = dict(working_directory=self._pyproject.project_path, verbose=self._pyproject.verbose)

        try:
            check_output(*command, "--quiet", **kwargs)
        except DetailedCalledProcessError:
            # re-run without the quiet switch so that the output appears in the console
            check_output(*command, **kwargs)

        return RunnerStatus.Success
