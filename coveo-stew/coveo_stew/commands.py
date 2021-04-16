"""Automates poetry operations in the repo."""

from pathlib import Path
import re
from typing import Set, Iterable, List, Union, Generator, Optional

import click
from coveo_functools.finalizer import finalizer
from coveo_styles.styles import echo, ExitWithFailure, install_pretty_exception_hook
from coveo_systools.filesystem import find_repo_root

from coveo_stew.configuration import VERBOSE, CI_MODE, DRY_RUN
from coveo_stew.discovery import find_pyproject, discover_pyprojects
from coveo_stew.exceptions import CheckFailed, RequirementsOutdated, PythonProjectNotFound
from coveo_stew.offline_publish import offline_publish
from coveo_stew.pydev import is_pydev_project, pull_and_write_dev_requirements
from coveo_stew.stew import PythonProject, PythonEnvironment


_COMMANDS_THAT_SKIP_INTRO_EMOJIS = ["locate"]


def _set_global_options(
    *,
    verbose: Optional[bool] = None,
    ci_mode: Optional[bool] = None,
    dry_run: Optional[bool] = None,
) -> None:
    if verbose is not None:
        VERBOSE.value = verbose
    if ci_mode is not None:
        CI_MODE.value = ci_mode
    if dry_run is not None:
        DRY_RUN.value = dry_run


def _echo_updated(updated: Set[Path]) -> None:
    """Used to print updated paths to the user."""
    if updated:
        echo.outcome("Updated:", pad_before=True)
        for updated_path in sorted(updated):
            if updated_path.is_absolute():
                # try to get a relative version of this path to beautify output.
                try:
                    updated_path = updated_path.relative_to(find_repo_root(default="."))
                except ValueError:
                    ...
            echo.noise(updated_path, item=True)


def _pull_dev_requirements() -> Generator[Path, None, None]:
    """Writes the dev-dependencies of pydev projects' local dependencies into pydev's pyproject.toml file."""
    dry_run_text = "(dry run) " if DRY_RUN else ""
    for pydev_project in discover_pyprojects(predicate=is_pydev_project):
        echo.step(f"Analyzing dev requirements for {pydev_project}")
        if pull_and_write_dev_requirements(pydev_project):
            echo.outcome(
                f"{dry_run_text}Updated {pydev_project.package.name} with new dev requirements."
            )
            if not DRY_RUN:
                echo.outcome("Lock file and virtual environment updated !!thumbs_up!!\n")
            yield pydev_project.toml_path
        else:
            echo.success(f"{pydev_project.package.name}'s dev requirements were up to date.")


@click.group()
@click.pass_context
def stew(ctx: click.Context) -> None:
    """The 'stew' cli entry point."""
    install_pretty_exception_hook()
    if ctx.invoked_subcommand not in _COMMANDS_THAT_SKIP_INTRO_EMOJIS:
        echo.step("!!sparkles!! !!snake!! !!sparkles!!")


@stew.command()
@click.option("--verbose", is_flag=True, default=None)
def check_outdated(verbose: Optional[bool] = None) -> None:
    """Return error code 1 if toml/lock are not in sync."""
    _set_global_options(verbose=verbose)
    echo.step("Analyzing all pyproject.toml files and artifacts:")
    outdated: Set[Path] = set()
    try:
        for project in discover_pyprojects():
            echo.noise(project, item=True)
            if not project.lock_path.exists() or project.lock_is_outdated:
                outdated.add(project.lock_path)
    except PythonProjectNotFound as exception:
        raise ExitWithFailure from exception

    try:
        outdated.update(_pull_dev_requirements())
    except PythonProjectNotFound:
        pass  # no pydev projects found.

    if outdated:
        raise ExitWithFailure(
            failures=outdated,
            suggestions='Run "poetry run pyproject fix-outdated" to update all outdated files.',
        ) from RequirementsOutdated(f"Found {len(outdated)} outdated file(s).")

    echo.success("Check complete! All files are up-to-date.")


@stew.command()
@click.option("--verbose", is_flag=True, default=None)
def fix_outdated(verbose: Optional[bool] = None) -> None:
    """Scans the whole repo and updates outdated pyproject-related files.

    Updates:
        - Lock files, only if their pyproject.toml was updated.
    """
    _set_global_options(verbose=verbose)
    echo.step("Synchronizing all outdated lock files:")
    updated: Set[Path] = set()
    with finalizer(_echo_updated, updated):
        try:
            for project in discover_pyprojects():
                echo.noise(project, item=True)
                if project.lock_if_needed():
                    updated.add(project.lock_path)
            try:
                updated.update(_pull_dev_requirements())
            except PythonProjectNotFound:
                pass  # no pydev projects found
        except PythonProjectNotFound as exception:
            raise ExitWithFailure from exception

    echo.success(f'Update complete! {len(updated) or "No"} file(s) were modified.\n')


@stew.command()
@click.option("--verbose", is_flag=True, default=None)
def bump(verbose: Optional[bool] = None) -> None:
    """Bumps locked versions for all pyprojects."""
    _set_global_options(verbose=verbose)
    updated: Set[Path] = set()
    with finalizer(_echo_updated, updated):
        try:
            for project in discover_pyprojects():
                echo.step(f"Bumping {project.lock_path}")
                if project.bump():
                    updated.add(project.toml_path)
        except PythonProjectNotFound as exception:
            raise ExitWithFailure from exception

    echo.success(f'Bump complete! {len(updated) or "No"} file(s) were modified.')


@stew.command()
@click.argument("project_name")
@click.option("--directory", default=None)
@click.option("--python", default=None)
@click.option("--verbose", is_flag=True, default=None)
def build(
    project_name: str,
    directory: Union[str, Path] = None,
    python: Union[str, Path] = None,
    verbose: Optional[bool] = None,
) -> None:
    """
    Store all dependencies of a python project into a local directory, according to its poetry.lock,
    for later use with `--find-links` and `--no-index`.

    --directory:
        IF unspecified and repo:    "repo_root/.wheels/*.whl"
        IF unspecified and no repo: "pyproject_folder/.wheels/*.whl"
        IF specified:               "directory/*.whl"
    """
    _set_global_options(verbose=verbose)
    try:
        project = find_pyproject(project_name)
    except PythonProjectNotFound as exception:
        raise ExitWithFailure from exception

    python_environments = (
        [PythonEnvironment(python)]
        if python
        else project.virtual_environments(create_default_if_missing=True)
    )

    if not directory:
        directory = (project.repo_root or project.project_path) / ".wheels"
    assert directory
    directory = Path(directory)

    echo.step(f"Building python project {project} in {directory}")
    for environment in python_environments:
        echo.outcome(f"virtual environment: {environment}", pad_before=True)
        offline_publish(project, directory, environment)

    echo.success()


@stew.command()
@click.argument("project_name", default=None, required=False)
@click.option("--verbose", is_flag=True, default=None)
def fresh_eggs(project_name: str = None, verbose: Optional[bool] = None) -> None:
    """
    Removes the egg-info from project folders.

    If launched from a folder containing a "pydev" project and "install" is true, reinstall
    the virtual environment (which recreates the egg-info).

    The egg-info is the "editable" install of your project. It allows you to modify the code between
    runs without reinstalling.

    Some behaviors (such as console entrypoints) are bootstrapped into the egg-info at install time, and
    won't be updated between runs. This is when this tool comes in handy.
    """
    _set_global_options(verbose=verbose)
    echo.step("Removing *.egg-info folders.")
    deleted = False
    try:
        for project in discover_pyprojects(query=project_name):
            if project.remove_egg_info():
                echo.outcome("Deleted: ", project.egg_path, item=True)
                deleted = True
    except PythonProjectNotFound as exception:
        raise ExitWithFailure from exception

    if deleted:
        echo.suggest("Environments were not refreshed. You may want to call 'poetry install'.")

    echo.success()


@stew.command()
@click.option("--dry-run", is_flag=True, default=None)
@click.option("--verbose", is_flag=True, default=None)
def pull_dev_requirements(dry_run: Optional[bool] = None, verbose: Optional[bool] = None) -> None:
    """Writes the dev-dependencies of pydev projects' local dependencies into pydev's pyproject.toml file."""
    _set_global_options(verbose=verbose, dry_run=dry_run)

    try:
        list(_pull_dev_requirements())
    except PythonProjectNotFound as exception:
        raise ExitWithFailure from exception


def _beautify_mypy_output(
    project: PythonProject, output: Iterable[str], *, full_paths: bool = False
) -> None:
    """Main use: guide IDEs by showing full paths to the files vs the current working directory.
    Bonus: highlight errors in red and display a slightly shortened version of the error output."""
    pattern = re.compile(
        rf"^(?P<path>{project.package.safe_name}.+):(?P<line>\d+):(?P<column>\d+(?::)| )"
        rf"(?:\s?error:\s?)(?P<detail>.+)$"
    )
    for line in output:
        match = pattern.fullmatch(line)
        if match:
            adjusted_path = project.project_path / Path(match["path"])
            adjusted_path = (
                adjusted_path.resolve()
                if full_paths
                else adjusted_path.relative_to(Path(".").resolve())
            )
            echo.error_details(
                f'{adjusted_path}:{match["line"]}:{match["column"]} {match["detail"]}'
            )
        else:
            echo.noise(line)


@stew.command()
@click.argument("project_name")
@click.option("--verbose", is_flag=True, default=None)
def locate(project_name: str, verbose: Optional[bool] = None) -> None:
    """Locate a python project (in the whole git repo) and print the directory containing the pyproject.toml file."""
    _set_global_options(verbose=verbose)
    try:
        echo.passthrough(find_pyproject(project_name).project_path)
    except PythonProjectNotFound as exception:
        # check for partial matches to guide the user
        partial_matches = (
            project.package.name for project in discover_pyprojects(query=project_name)
        )
        try:
            raise ExitWithFailure(
                suggestions=(
                    "Exact match required but partial matches were found:",
                    *partial_matches,
                )
            ) from exception
        except PythonProjectNotFound:
            # we can't find a single project to suggest; raise the original exception.
            raise ExitWithFailure from exception


@stew.command()
@click.argument("project_name", default=None, required=False)
@click.option("--exact-match", is_flag=True, default=None)
@click.option("--verbose", is_flag=True, default=None)
def refresh(
    project_name: str = None, exact_match: bool = None, verbose: Optional[bool] = None
) -> None:
    _set_global_options(verbose=verbose)
    echo.step("Refreshing python project environments...")
    pydev_projects = []
    try:
        for project in discover_pyprojects(query=project_name, exact_match=exact_match):
            if project.options.pydev:
                pydev_projects.append(project)
                continue  # do these at the end
            echo.normal(project, pad_before=True, pad_after=True, emoji="hourglass")
            project.refresh()
    except PythonProjectNotFound as exception:
        raise ExitWithFailure from exception

    for project in pydev_projects:
        echo.normal(project, pad_before=True, pad_after=True, emoji="hourglass")
        if project.current_environment_belongs_to_project():
            echo.warning(f"Cannot update {project} because it's what we're currently running.")
        else:
            project.refresh()

    echo.success()


@stew.command()
@click.argument("project_name", default=None, required=False)
@click.option("--exact-match", is_flag=True, default=None)
@click.option("--fix/--no-fix", default=False)
@click.option("--check", multiple=True, default=None)
@click.option("--verbose", is_flag=True, default=None)
def ci(
    project_name: str = None,
    exact_match: Optional[bool] = None,
    fix: bool = False,
    check: List[str] = None,
    verbose: Optional[bool] = None,
) -> None:
    """Launches continuous integration runners on all environments."""
    _set_global_options(verbose=verbose, ci_mode=exact_match)

    failures = []
    try:
        for project in discover_pyprojects(query=project_name, exact_match=exact_match):
            echo.step(project.package.name, pad_after=False)
            if not project.launch_continuous_integration(auto_fix=fix, checks=check):
                failures.append(project)
    except PythonProjectNotFound as exception:
        raise ExitWithFailure from exception

    if failures:
        raise ExitWithFailure(failures=failures) from CheckFailed(
            f"{len(failures)} project(s) failed ci steps."
        )

    echo.success()
