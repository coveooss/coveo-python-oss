from coveo_pyproject.ci.runner import ContinuousIntegrationRunner, RunnerStatus
from coveo_pyproject.environment import PythonEnvironment, PythonTool, coveo_pyproject_environment
from coveo_systools.subprocess import check_output


class PoetryCheckRunner(ContinuousIntegrationRunner):
    name: str = "poetry-check"
    check_failed_exit_codes = [1]

    def _launch(self, environment: PythonEnvironment, *extra_args: str) -> RunnerStatus:
        assert environment  # we don't use this one; marking for linters to :chut:
        check_output(
            *coveo_pyproject_environment.build_command(PythonTool.Poetry, "check"),
            working_directory=self._pyproject.project_path
        )
        return RunnerStatus.Success
