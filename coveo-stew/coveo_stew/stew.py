"""Interact with python projects programmatically."""

import os
from pathlib import Path
import re
import shutil
from shutil import rmtree
import sys
from typing import Generator, Optional, Type, Any, List

from coveo_functools.casing import flexfactory
from coveo_itertools.lookups import dict_lookup
from coveo_styles.styles import echo
from coveo_systools.filesystem import find_repo_root, CannotFindRepoRoot
from coveo_systools.subprocess import check_run, DetailedCalledProcessError
from poetry.factory import Factory

from coveo_stew.ci.config import ContinuousIntegrationConfig
from coveo_stew.ci.runner import RunnerStatus
from coveo_stew.environment import PythonEnvironment, coveo_stew_environment, PythonTool
from coveo_stew.exceptions import PythonProjectNotFound, PythonProjectException
from coveo_stew.metadata.stew_api import StewPackage
from coveo_stew.metadata.poetry_api import PoetryAPI
from coveo_stew.metadata.pyproject_api import PythonProjectAPI, T_PythonProject
from coveo_stew.metadata.python_api import PythonFile
from coveo_stew.utils import load_toml_from_path


class PythonProject(PythonProjectAPI):
    """Access the information within a pyproject.toml file and operate on them."""

    def __init__(self, project_path: Path, *, verbose: bool = False) -> None:
        self.verbose = verbose
        self.project_path: Path = (
            project_path if project_path.is_dir() else project_path.parent
        ).absolute()
        self.toml_path: Path = self.project_path / PythonFile.PyProjectToml
        self.lock_path: Path = self.project_path / PythonFile.PoetryLock

        toml_content = load_toml_from_path(self.toml_path)

        self.package: PoetryAPI = flexfactory(
            PoetryAPI, **dict_lookup(toml_content, "tool", "poetry"), _pyproject=self
        )
        self.egg_path: Path = self.project_path / f"{self.package.safe_name}.egg-info"

        self.options: StewPackage = flexfactory(
            StewPackage,
            **dict_lookup(toml_content, "tool", "stew", default={}),
            _pyproject=self,
        )

        if self.options.pydev:
            # ensure no steps are repeated. pydev projects only receive basic poetry/lock checks
            self.ci: ContinuousIntegrationConfig = ContinuousIntegrationConfig(
                check_outdated=True, poetry_check=True, mypy=False, _pyproject=self
            )
        else:
            self.ci = flexfactory(
                ContinuousIntegrationConfig,
                **dict_lookup(toml_content, "tool", "stew", "ci", default={}),
                _pyproject=self,
            )

        # these are the actual poetry apis
        self.poetry = Factory().create_poetry(self.project_path)

        try:
            repo_root: Optional[Path] = find_repo_root(self.project_path)
        except CannotFindRepoRoot:
            repo_root = None

        self.repo_root: Optional[Path] = repo_root

    def relative_path(self, path: Path) -> Path:
        """returns the relative path of a path vs the project folder."""
        return path.relative_to(self.project_path)

    @classmethod
    def find_pyproject_paths(cls, path: Path) -> Generator[Path, None, None]:
        """Subclasses may override this to change/filter discovery."""
        yield from path.rglob(f"{PythonFile.PyProjectToml}")

    @classmethod
    def find_pyproject(
        cls: Type[T_PythonProject], project_name: str, path: Path = None, *, verbose: bool = False
    ) -> T_PythonProject:
        project = next(
            cls.find_pyprojects(path, query=project_name, exact_match=True, verbose=verbose), None
        )
        if not project:
            raise PythonProjectNotFound(f"{project_name} cannot be found in {path}")
        return project

    @classmethod
    def find_pyprojects(
        cls: Type[T_PythonProject],
        path: Path = None,
        *,
        query: str = None,
        exact_match: bool = False,
        verbose: bool = False,
    ) -> Generator[T_PythonProject, None, None]:
        """Factory; scan a path (recursive) and return a PythonProject instance for each pyproject.toml

        Parameters:
            path: where to start looking for pyproject.toml files.
            query: substring for package selection. '-' and '_' are equivalent.
            exact_match: turns query into an exact match (except for - and _). Recommended use: CI scripts
            verbose: output more details to command line
        """
        if not path:
            path = find_repo_root(default=".")

        if exact_match and not query:
            raise PythonProjectNotFound("An exact match was requested but no query was provided.")

        count_projects = 0
        for poetry_file in cls.find_pyproject_paths(path):
            project = cls(poetry_file, verbose=verbose)
            if verbose:
                echo.noise("PyProject found: ", project)

            if (
                not query
                or (exact_match and project.package.name == query)
                or (
                    not exact_match
                    and query.replace("-", "_").lower() in project.package.safe_name.lower()
                )
            ):
                count_projects += 1
                yield project

        if count_projects == 0:
            raise PythonProjectNotFound(
                f"Cannot find any project that could match {query}"
                if query
                else "No python projects were found."
            )

    @property
    def lock_is_outdated(self) -> bool:
        """True if the toml file has pending changes that were not applied to poetry.lock"""
        if not self.lock_path.exists():
            return False
        return not self.poetry.locker.is_fresh()

    def virtual_environments(
        self, *, create_default_if_missing: bool = False
    ) -> List[PythonEnvironment]:
        """The project's virtual environments.

        create_default_if_missing: When no environments are found, create an empty environment using what poetry
            would use by default. The environment will have the interpreter, pip, setuptools, pkg-resources and
            the current project installed. No other dependencies will be installed.
        """
        environments = []
        for str_path in self.poetry_run(
            "env", "list", "--full-path", capture_output=True, breakout_of_venv=True
        ).split("\n"):
            if str_path.strip():
                path = Path(str_path.replace("(Activated)", "").strip())
                environments.append(PythonEnvironment(path))

        if not environments and create_default_if_missing:
            # when we call `poetry run <cmd>` on a project, poetry will create the environment if it doesn't exist.
            self.poetry_run("run", "python", "--version")
            environments = self.virtual_environments()

        return environments

    def current_environment_belongs_to_project(self) -> bool:
        """True if we're running from one of the project's virtual envs.
        Typically False; serves the rare cases where stew is installed inside the environment.
        """
        current_executable = Path(sys.executable)
        return any(
            environment.python_executable == current_executable
            for environment in self.virtual_environments()
        )

    def bump(self) -> bool:
        """Bump (update) all dependencies to the lock file. Return True if changed."""
        if not self.lock_path.exists():
            return self.lock_if_needed()

        content = self.lock_path.read_text()
        self.poetry_run("update", "--lock", breakout_of_venv=True)
        if content != self.lock_path.read_text():
            return True
        return False

    def build(self, target_path: Path = None) -> Path:
        """Builds the package's wheel. If a path is provided, it will be moved there.
        Returns final path to the artifact."""
        # like coredump_detector-0.0.1-py3-none-any.whl
        wheel_pattern = re.compile(r"(?P<distribution>\S+?)-(?P<version>.+?)-(?P<extra>.+)\.whl")
        poetry_output = self.poetry_run("build", "--format", "wheel", capture_output=True)
        wheel_match = wheel_pattern.search(poetry_output)

        if not wheel_match:
            raise PythonProjectException(
                f"Unable able to find a wheel filename in poetry's output:\n{poetry_output}"
            )

        assert wheel_match["distribution"] == self.package.safe_name
        assert wheel_match["version"] == str(self.package.version)
        wheel = (
            self.project_path / "dist" / Path(wheel_match.group())
        )  # group() gives the complete match
        assert wheel.exists(), f"{wheel} cannot be found."

        if target_path is None:
            # no move necessary; we're done
            return wheel

        target = target_path / wheel.name
        if not target_path.exists():
            target_path.mkdir(parents=True)
        assert target_path.is_dir()
        shutil.move(str(wheel), str(target))

        return target

    def launch_continuous_integration(self, auto_fix: bool = False) -> bool:
        """Launch all continuous integration runners on the project."""
        if self.ci.disabled:
            return True

        exceptions: List[DetailedCalledProcessError] = []
        for runner in self.ci.runners:
            for environment in self.virtual_environments(create_default_if_missing=True):
                try:
                    echo.normal(
                        f"{runner} ({environment.pretty_python_version})", emoji="hourglass"
                    )
                    status = runner.launch(environment, auto_fix=auto_fix)
                    if status is not RunnerStatus.Success:
                        echo.warning(
                            f"{self.package.name}: {runner} reported issues:",
                            pad_before=False,
                            pad_after=False,
                        )
                        runner.echo_last_failures()

                except DetailedCalledProcessError as exception:
                    echo.error(
                        f"The ci runner {runner} failed to complete "
                        f"due to an environment or configuration error."
                    )
                    exceptions.append(exception)

        if exceptions:
            if len(exceptions) > 1:
                echo.warning(f"{len(exceptions)} exceptions found; raising first one.")
            raise exceptions[0]

        return all(runner.status is RunnerStatus.Success for runner in self.ci.runners)

    def install(self, remove_untracked: bool = True, quiet: bool = False) -> None:
        """
        Performs a 'poetry install --remove-untracked' on the project. If an environment is provided, target it.
        """
        command = ["install"]
        if remove_untracked:
            command.append("--remove-untracked")
        if quiet:
            command.append("--quiet")
        self.poetry_run(*command)

    def remove_egg_info(self) -> bool:
        """Removes the egg-info (editable project hook) from the folder. Returns True if we removed it."""
        if self.egg_path.exists():
            rmtree(str(self.egg_path))
            return True
        return False

    def refresh(self) -> None:
        """Removes a virtual environment and then performs install."""
        self.remove_egg_info()
        self.poetry_run("env", "remove", "python", breakout_of_venv=True)
        self.lock_if_needed()
        self.install()

    def lock_if_needed(self) -> bool:
        """Lock if needed, return True if ran."""
        if not self.lock_path.exists() or self.lock_is_outdated:
            self.poetry_run("lock", breakout_of_venv=True)
            return True
        return False

    def poetry_run(
        self, *commands: Any, capture_output: bool = False, breakout_of_venv: bool = True
    ) -> Optional[str]:
        """internal run-a-poetry-command."""
        # we use the poetry executable from our dependencies, not from the project's environment!
        poetry_env = coveo_stew_environment
        if not poetry_env.poetry_executable.exists():
            raise PythonProjectException(
                f"Poetry was not found; expected to be somewhere around {poetry_env.python_executable}?"
            )

        environment_variables = os.environ.copy()
        if breakout_of_venv:
            environment_variables.pop("VIRTUAL_ENV", None)

        return check_run(
            *poetry_env.build_command(PythonTool.Poetry, *commands, "-vv" if self.verbose else ""),
            working_directory=self.project_path,
            capture_output=capture_output,
            verbose=self.verbose,
            env=environment_variables,
        )

    def __str__(self) -> str:
        return f"{self.package.name} [{self.toml_path}]"
