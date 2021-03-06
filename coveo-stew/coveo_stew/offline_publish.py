import functools
import json
from pathlib import Path
from typing import Set, Dict, cast, List, Optional

from coveo_styles.styles import echo
from coveo_systools.subprocess import check_call, check_output
from poetry.core.packages import Package

from coveo_stew.environment import PythonEnvironment, PythonTool
from coveo_stew.exceptions import PythonProjectException
from coveo_stew.metadata.pyproject_api import PythonProjectAPI


_DEFAULT_PIP_OPTIONS = (
    "--disable-pip-version-check",
    "--no-input",
    "--exists-action",
    "i",
    "--pre",
)


def offline_publish(
    project: PythonProjectAPI,
    wheelhouse: Path,
    environment: PythonEnvironment,
    *,
    quiet: bool = False,
) -> None:
    """
    Store the project and all its locked dependencies into a folder, so that it can be installed offline using pip.

    Some packages provide wheels specific to an interpreter's version/abi/platform/implementation. It's important
    to use the right environment here because the files may differ and `pip install --no-index` will not work.
    """
    _OfflinePublish(project, wheelhouse, environment).perform_offline_install(quiet=quiet)


class _OfflinePublish:
    """
    this class is taking the long route to obtain the dependencies because of two issues in poetry:
        https://github.com/python-poetry/poetry/issues/3254
        https://github.com/python-poetry/poetry/issues/3189

    once they're fixed, most of the code below can be removed in favor of:
        poetry export --format requirements.txt --no-dev --output requirements.txt
        pip wheel -r requirements.txt --target target_path --find-links target_path
    """

    def __init__(
        self, project: PythonProjectAPI, wheelhouse: Path, environment: PythonEnvironment
    ) -> None:
        self.project = project
        self.environment = environment
        self.wheelhouse = wheelhouse
        self._check_call = functools.partial(
            check_call if self.verbose else check_output, verbose=self.verbose
        )

        self._valid_packages: Optional[Set[str]] = None
        self._local_projects: Set[str] = {
            name
            for (name, package) in self.project.package.all_dependencies.items()
            if package.path
        }
        self._locked_packages: Dict[str, Package] = {
            package.name: package
            for package in self.project.poetry.locker.locked_repository().packages
        }

    @property
    def verbose(self) -> bool:
        return self.project.verbose

    @property
    def valid_packages(self) -> Set[str]:
        if self._valid_packages is None:
            if self.environment in list(self.project.virtual_environments()):
                pip_freeze_environment = self.environment
            else:
                pip_freeze_environment = next(
                    self.project.virtual_environments(create_default_if_missing=True)
                )
                echo.warning(
                    f"The executable {self.environment} is not part of this project. "
                    f'To fix this, run "poetry env use {self.environment.python_executable}". '
                )
            echo.noise(f"Inspecting packages in {pip_freeze_environment}")
            pip_freeze = cast(
                List[Dict[str, str]],
                json.loads(
                    check_output(
                        *pip_freeze_environment.build_command(
                            PythonTool.Pip, "list", "--format", "json", *_DEFAULT_PIP_OPTIONS
                        ),
                        verbose=self.verbose,
                    )
                ),
            )
            self._valid_packages = {freezed["name"].lower() for freezed in pip_freeze}
        assert self._valid_packages is not None
        return self._valid_packages

    def perform_offline_install(self, *, quiet: bool = False) -> None:
        """ Performs all the operation for the offline install. """
        if not self.project.lock_path.exists():
            raise PythonProjectException("Project isn't locked; can't proceed.")

        self.project.install(remove_untracked=False, quiet=quiet)
        self.project.build(self.wheelhouse)
        self._store_setup_dependencies_in_wheelhouse(self.project)
        self._store_dependencies_in_wheelhouse()

        # validate the wheelhouse; this will exit in error if something's amiss or result in a noop if all is right.
        self._validate_package(f"{self.project.package.name}=={self.project.package.version}")

    def _store_setup_dependencies_in_wheelhouse(self, project: PythonProjectAPI = None) -> None:
        """store the build dependencies in the wheelhouse, like setuptools.
        Eventually pip/poetry will play better and this won't be necessary anymore"""
        project = project or self.project
        for dependency in project.options.build_dependencies.values():
            dep = (
                dependency.name
                if dependency.version == "*"
                else f"{dependency.name}{dependency.version}"
            )  # such as setuptools>=42
            self._check_call(
                *self.environment.build_command(PythonTool.Pip, "wheel", dep),
                working_directory=self.wheelhouse,
            )

    def _store_dependencies_in_wheelhouse(self) -> None:
        """ Store the dependency wheels in the wheelhouse. """
        # temporary mitigation of circular import
        from coveo_stew.discovery import find_pyproject

        # prepare the pip wheel call
        to_download: Set[Package] = set()
        index_urls: Set[str] = set()

        for requirement in self.valid_packages:
            if requirement not in self._locked_packages:
                continue  # could be a dev dependency, or something the dev installed
            if requirement in self._local_projects:
                # we can build this one from disk
                local_dependency = find_pyproject(requirement)
                self._store_setup_dependencies_in_wheelhouse(local_dependency)
                local_dependency.build(self.wheelhouse)
            else:
                # use the version from the locker, not from the installed packages
                locked_dependency = self._locked_packages[requirement]
                to_download.add(locked_dependency)
                if locked_dependency.source_url:
                    index_urls.add(locked_dependency.source_url)

        self._call_pip_wheel(*to_download, index_urls=index_urls)

    def _call_pip_wheel(self, *packages: Package, index_urls: Set[str] = None) -> None:
        """ Call pip wheel to download the packages, with optional extra index urls. """
        if not packages:
            return

        command = self.environment.build_command(
            PythonTool.Pip,
            "wheel",
            *(f"{requirement.name}=={requirement.version}" for requirement in packages),
            "--wheel-dir",
            self.wheelhouse,
            "--no-deps",
            "--no-cache-dir",
            *_DEFAULT_PIP_OPTIONS,
        )

        if index_urls:
            command += "--index-url", index_urls.pop()
            for extra_url in index_urls:
                command += "--extra-index-url", extra_url

        self._check_call(*command)

    def _validate_package(self, package_specification: str) -> None:
        """Validates that a package and all its dependencies can be resolved from the wheelhouse.
        Package specification can be a name like `coveo-functools` or a constraint like `coveo-functools>=0.2.1`"""
        self._check_call(
            *self.environment.build_command(
                PythonTool.Pip,
                "wheel",
                package_specification,
                "--find-links",
                self.wheelhouse,
                "--wheel-dir",
                self.wheelhouse,
                "--no-index",
                *_DEFAULT_PIP_OPTIONS,
            ),
            working_directory=self.wheelhouse,
        )
