"""Utils that deal with the filesystem."""
import subprocess
from contextlib import contextmanager
from filecmp import cmp
import functools
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from typing import Union, Iterator, Generator, Optional

from .subprocess import check_output, DetailedCalledProcessError


class CannotFindRepoRoot(Exception):
    ...


@contextmanager
def pushd(working_directory: Union[Path, str]) -> Iterator[None]:
    """Change the current working directory for a block of code."""
    cwd = os.getcwd()
    try:
        os.chdir(working_directory)
        yield
    finally:
        os.chdir(cwd)


def find_paths(
    path_to_find: Path,
    search_from: Path = None,
    *,
    in_root: bool = False,
    in_parents: bool = False,
    in_children: bool = False,
) -> Generator[Path, None, None]:
    """
    Generic utility to find files from python.

    Search and yield valid instances of `path_to_find`,
    in `search_from`, its parents or children, in that order.

    parameters:
        path_to_find: The path we are looking for.
                      Can be simple:    Path('file.txt') Path('folder')
                      or relative:      Path('../python-folder')
                      or very specific: Path('python-folder/pyproject.toml')
        search_from: Search will start in this folder.
                     When not specified, the current working directory is used.
        in root: Include results directly in search_from.
        in_parents: Include results in search_from's parent folders.
        in_children: Include results in search_from's folders.
    """
    if search_from is None:
        search_from = Path(".")

    if not search_from.is_dir():
        raise FileNotFoundError(f"Cannot search from ({search_from}): not an existing directory.")

    if in_root and (search_from / path_to_find).exists():
        yield (search_from / path_to_find).resolve()

    if in_parents:
        current = search_from.parent
        while True:
            tentative_path = current / path_to_find
            if tentative_path.exists():
                yield tentative_path
            current = current.parent
            if len(current.parts) == 1:
                break

    if in_children:
        yield from search_from.rglob(str(path_to_find))


def find_application(
    name: str, *, path: str = None, raise_if_not_found: bool = False
) -> Optional[Path]:
    """Finds an application using the shell (e.g.: which).

    path: https://docs.python.org/3/library/shutil.html#shutil.which
          When no path is specified, the results of os.environ() are used, returning
          either the “PATH” value or a fallback of os.defpath.
    """
    executable = shutil.which(name, path=path)
    if executable:
        return Path(executable.strip()).absolute()
    if raise_if_not_found:
        raise FileNotFoundError(f"{name} cannot be located.")
    return None


@functools.lru_cache(maxsize=1)
def _which_git() -> Optional[Path]:
    """Returns the path to the git executable if it can be found."""
    return find_application("git")


@functools.lru_cache(maxsize=32)
def _find_repo_root(path: Path) -> Path:
    """internal, lru_cache implemented to work vs multiple repos (requires absolute paths)"""
    assert path.is_absolute()

    git = _which_git()
    git_error: Optional[DetailedCalledProcessError] = None
    if git:
        try:
            with pushd(path):
                return Path(
                    check_output(git, "rev-parse", "--show-toplevel", stderr=subprocess.STDOUT)
                )
        except DetailedCalledProcessError as exception:
            git_error = exception

    git_evidence = next(find_paths(Path(".git"), path, in_root=True, in_parents=True), None)
    if git_evidence:
        assert git_evidence.is_dir()
        return git_evidence.parent

    raise CannotFindRepoRoot(
        "Cannot find a .git folder in order to locate repo's root."
    ) from git_error


def find_repo_root(path: Union[Path, str] = ".", *, default: Union[str, Path] = None) -> Path:
    """Will find the root of a git repo based on the provided path.

    Will raise FileNotFoundError if it cannot be found.

    Parameters:
        path: The path where to start searching.
        default: If set, return this path (as absolute) instead of raising an exception.
    """
    try:
        return _find_repo_root(Path(path).absolute())
    except CannotFindRepoRoot:
        if default is not None:
            return Path(default).absolute()
        raise


def replace_if_different(new_file: Path, to_overwrite: Path) -> bool:
    """Returns True if replaced. Always deletes new_file. Reads both files entirely."""
    identical: bool = to_overwrite.exists() and cmp(str(to_overwrite), str(new_file))

    if identical:
        new_file.unlink()
    else:
        new_file.replace(to_overwrite)

    return not identical


def _safe_text_write_dry_run(target: Path, content: str, *, only_if_changed: bool = False) -> bool:
    if only_if_changed:
        return not target.exists() or target.read_text().strip() != content.strip()
    return True


def safe_text_write(
    target: Path, content: str, *, only_if_changed: bool = False, dry_run: bool = False
) -> bool:
    """Writes a text file to a temporary location then replaces target.
    Returns True if the file ("would be" if dry_run else "was") overwritten."""
    if dry_run:
        return _safe_text_write_dry_run(target, content, only_if_changed=only_if_changed)

    with TemporaryDirectory() as folder:
        file = Path(folder) / target.name
        file.write_text(content)
        if only_if_changed:
            return replace_if_different(file, target)
        file.replace(target)
        return True
