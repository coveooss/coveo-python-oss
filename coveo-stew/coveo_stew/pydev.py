"""
Projects marked as pydev behave as "one ring to rule them all"; its `pyproject.toml` file links most/all of the
python projects in a repository for developer convenience.

It has some additional features and tricks that do not apply to other projects. This is centralized here.
"""

from typing import Generator, Tuple, Set, Any

from coveo_systools.filesystem import safe_text_write
import tomlkit
from tomlkit.items import item as toml_item, Item as TomlItem, Table

from coveo_stew.exceptions import PythonProjectException
from coveo_stew.stew import PythonProject


class NotPyDevProject(PythonProjectException):
    ...


def is_pydev_project(project: PythonProject) -> bool:
    """Returns true when a project is a pydev project. Typically used as a predicate for `discover_pyprojects`."""
    return project.options.pydev


def pull_and_write_dev_requirements(project: PythonProject, *, dry_run: bool = False) -> bool:
    """Pulls the dev requirement from dependencies into pydev's dev requirements."""
    if not project.options.pydev:
        raise NotPyDevProject(f"{project.project_path}: Not a PyDev project.")

    # prepare a toml container for our data
    toml = tomlkit.loads(project.toml_path.read_text())
    all_dev_dependencies: Table = tomlkit.table()

    # extract the dev requirements from the local dependencies
    for item in sorted(_dev_dependencies_of_dependencies(project)):
        all_dev_dependencies.add(*item)

    # the py dev environment package has no code, no tests, no entrypoints, no nothin'!
    # as such, dev dependencies are irrelevant; we reserve the section for the current purpose.
    all_dev_dependencies.comment(  # type: ignore[attr-defined]
        "pydev projects' dev-dependencies are autogenerated; do not edit manually!"
    )
    toml["tool"]["poetry"]["dev-dependencies"] = all_dev_dependencies  # type: ignore[index]

    if safe_text_write(
        project.toml_path,
        "\n".join(_format_toml(tomlkit.dumps(toml))),
        only_if_changed=True,
        dry_run=dry_run,
    ):
        if not dry_run and project.lock_if_needed():
            project.install()
        return True
    return False


def _format_toml(toml_content: str) -> Generator[str, None, None]:
    """tomlkit sometimes forgets to add empty lines before sections."""
    first = True
    for line in toml_content.split("\n"):
        if not first and line.strip().startswith("["):
            yield "\n"  # extra empty line between each section means 2 empty lines between sections
        if line.strip():
            yield line
        first = False


def _dev_dependencies_of_dependencies(
    project: PythonProject,
) -> Generator[Tuple[str, TomlItem], None, None]:
    """Yields the dev dependencies of this project's dependencies."""
    # we mark our direct dependencies as seen, so that we don't duplicate them in the dev section.
    seen: Set[str] = set(project.package.dependencies)
    # we only care about local non-dev dependencies from the project.
    for dependency in filter(lambda _: _.is_local, project.package.dependencies.values()):
        assert not dependency.path.is_absolute()
        project = PythonProject(project.project_path / dependency.path, verbose=project.verbose)
        new = set(project.package.dev_dependencies).difference(seen)
        seen.update(new)
        for dev_dependency in (project.package.dev_dependencies[_] for _ in new):
            if dev_dependency.is_local:
                value: Any = tomlkit.inline_table()
                value.append("path", str(dev_dependency.path.relative_to(project.project_path)))
            else:
                value = dev_dependency.version
            yield dev_dependency.name, toml_item(value)
