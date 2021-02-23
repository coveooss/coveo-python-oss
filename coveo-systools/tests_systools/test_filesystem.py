from pathlib import Path
from typing import Iterator
from unittest import mock

import pytest
from coveo_systools.filesystem import find_application, find_paths, find_repo_root
from coveo_testing.markers import UnitTest


@UnitTest
def test_cannot_find_application() -> None:
    with mock.patch("shutil.which", return_value=None):
        assert find_application("meh") is None


@UnitTest
def test_raise_cannot_find_application() -> None:
    with mock.patch("shutil.which", return_value=None):
        with pytest.raises(FileNotFoundError):
            _ = find_application("meh", raise_if_not_found=True)


@UnitTest
def test_find_application() -> None:
    assert find_application("python")


@UnitTest
def test_git_root() -> None:
    git_root = find_repo_root(__file__)
    assert (git_root / ".github").exists()
    assert (git_root / "coveo-systools").is_dir()


@UnitTest
def test_find_paths() -> None:
    query = Path("pyproject.toml"), find_repo_root(__file__)

    def _count(iterator: Iterator[Path]) -> int:
        return len(list(iterator))

    count_in_root = _count(find_paths(*query, in_root=True))
    count_in_children = _count(find_paths(*query, in_children=True))
    count_in_parents = _count(find_paths(*query, in_parents=True))

    assert count_in_root == 1
    assert count_in_children > 1
    assert sum((count_in_parents, count_in_children, count_in_root)) == _count(
        find_paths(*query, in_root=True, in_children=True, in_parents=True)
    )
    assert _count(find_paths(*query)) == 0
