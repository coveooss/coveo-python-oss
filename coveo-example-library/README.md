# coveo-example-library

This project serves as an example / template for the structure used by all python projects in the `coveo-python-oss` repository.
The conventions and rules are explained below.

All paths in the document are relative to the root of the `coveo-python-oss` repo.


## Rules and Conventions

### project name

The project is named in lowercase with spaces substituted for dashes `-`:

    name: coveo-example-library


### project folder

The project folder uses the project name:

    /coveo-example-library


### source folder

The source folder is the project name in camel case and contains an `__init__.py` file:

    /coveo-example-library/coveo_example_library/__init__.py


### pyproject.toml

The latest standard is to use the `pyproject.toml` file for everything that supports it!
Every project must provide one. It is located in the project folder.

    /coveo-example-library/pyproject.toml


## poetry

[Poetry](https://github.com/python-poetry/poetry) must be used in order to be able to get through the CI process.


## tests

The library has tests that are understood by pytest.
The test folder name is the library's import name prefixed with "tests_" and contain an `__init__.py` file: 

    /coveo-example-library/tests_coveo_example_library/__init__.py

Why: If all projects used a `tests` folder, IDEs may get confused trying to inspect symbols.
Pycharm for instance will not import a 2nd folder of the same name; only the first one is found.
Different names ensure that these mechanisms don't conflict.


## type annotations

The library _and its tests_ must be fully type annotated. Both folders must have a `py.typed` folder
so that they're picked up by the type checker during CI.

The mypy configuration is at the root of the repository and is intentionally strict.

    /coveo-example-library/coveo_example_libary/py.typed
    /coveo-example-library/tests_coveo_example_libary/py.typed
    /mypy.ini


## versioning and publishing

All libraries are published on `pypi.org` automatically.
Versioning uses a major.minor.revision format. 

Developers are expected to understand and apply semantic versioning practices and bump the minor/major accordingly.

Revision bumps are automatic:
- When the CI detects changes, it will pull the latest published version from `pypi.org`.
- It will then bump the revision number (e.g. `0.1.0` becomes `0.1.1`) then push it

To bump major or minor:
- Set the new version in the `pyproject.toml` file (e.g.: `0.2.0`)
- CI will detect that latest is `0.1.1` but decides to use `0.2.0` since that's newer.
- Subsequent runs will detect `0.2.0` as the latest and will publish `0.2.1`, `0.2.2` and so on.
