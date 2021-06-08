from coveo_stew.ci.runner import ContinuousIntegrationRunner, RunnerStatus
from coveo_stew.environment import PythonEnvironment, PythonTool
from coveo_systools.subprocess import check_output


class PydocStyleRunner(ContinuousIntegrationRunner):
    name: str = "pydocstyle"
    check_failed_exit_codes = [1]
    outputs_own_report = True

    def _launch(self, environment: PythonEnvironment, *extra_args: str) -> RunnerStatus:
        if not environment.pydocstyle_executable.exists():
            self._last_output.append("PyDocStyle executable could not be found")
            return RunnerStatus.Error

        command = environment.build_command(
            PythonTool.PydocStyle,
            '--arg'
        )


        check_output(
            *command,
            *extra_args,
            working_directory=self._pyproject.project_path,
            verbose=self._pyproject.verbose,
        )

        return RunnerStatus.Success
