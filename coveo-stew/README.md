# coveo-stew

Extra magic for poetry-backed projects with CI and batch operations in mind.


## Use cases

- You don't want to spend time writing the setup/test/report/publish/tag CI workflow
- You want to work with multiple python projects in a single repository
- You need a way to download locked dependencies and install them offline later


# Features

## poetry on steroids / offline distribution
- Orchestrates several isolated poetry projects in one repo
- Supports unpublished, local-only libraries and projects
- Generates offline installation package from lock files

## developer tools
- Batch support for common operations, such as poetry lock and poetry install
- Specialized development environment support (called pydev)

## ci tools
- Builtin, config-free pytest and mypy checks
- Able to resolve some checks automatically (e.g.: lock file is outdated? call poetry lock!)
- JUnit report generation
- Github action


# Installation

It is recommended to install using [pipx](https://github.com/pipxproject/pipx) in order to isolate this into a nice little space:

```
pip3 install pipx --user
pipx install coveo-stew
```

If you don't use pipx, make sure to isolate the installation into a virtual environment, otherwise it may interfere with an existing poetry installation.


# Commands

## General command usage

Unless a project name is specified, most commands will operate on all projects in a git repository based on the current working folder:

- `stew <command>`
    - Perform a command on all projects
- `stew <command> --help`
    - Obtain help about a particular command
- `stew <command> <project-name>`
    - Perform the command on all projects with `<project-name>` in their name (partial match)
- `stew <command> <project-name> --exact-match`
    - Disable partial project name matching

The main commands are summarized below.


## `stew ci`

Orchestrates the CI process over one or multiple projects. 

Errors will show in the console and in junit xml reports generated inside the `.ci` folder.

Configuration is done through each `pyproject.toml` file; default values are shown:

```
[tool.stew.ci]
mypy = true
poetry-check = true
check-outdated = true
pytest = false
offline-build = false
```

The value type of these items is designed to be extensible. For instance, the pytest runner allows you to configure the markers for the ci run:

```
[tool.stew.ci]
pytest = { marker_expression = 'not docker_tests' }
```


## `stew build`

Store the project and its **locked dependencies** to disk. 

Optimally used to create truly repeatable builds and workflows (e.g.: docker images, terraform, S3, puppet...)

The folder can later be installed offline with `pip install --no-index --find-links <folder> <project-name>`

**Make sure your target `<folder>` is clean**: Keep in mind that `pip` will still use the `pyproject.toml` constraints when installing, not `poetry.lock`. 
The system works when the locked version is the only thing that `pip` can find in the `<folder>`.


### `stew fix-outdated`

Checks for out-of-date files and automatically updates them.

Summary of actions:
- `poetry lock` if `pyproject.toml` changed but not the `poetry.lock`
- `stew pull-dev-requirements` if a pydev project's dev-requirements are out of sync


### `stew bump`

Calls `poetry lock` on all projects.


# How to depend on a local library

We leverage poetry's `path` constraint in a very specific way:

```
[tool.poetry.dependencies]
my-package = { version = "^2.4" }

[tool.poetry.dev-dependencies]
my-package = { path = "../my-package/" }
```

Essentially, the behavior we're looking for:

- Through `pip install`, it will obtain the latest `^2.4` from `pypi.org`
- Through `poetry install`, which is only meant for development, the source is fetched from the disk


# pydev (development environment)

A repo-wide `pyproject.toml` is available at the root, which refers to the projects by path. 
This is a development bootstrap for development convenience, so that one can work in any of the projects of the repository without having to configure multiple environments in the IDE.

## How to enable pydev

This functionality is enabled by adding the following to your `pyproject.toml`:

```
[tool.stew]
pydev = true
```

The marker above comes with a few behavior differences in the way it interacts with stew and poetry:

- it cannot be packaged, published or even pip-installed
- `stew ci` will skip it
- the `tool.poetry.dev-dependencies` section is reserved, can be generated and updated through stew's `pull-dev-requirements` and `fix-outdated` commands

As such, the pydev functionality is only suitable to enable seamless development between python projects in the repository.

## How to use pydev

1. Call `poetry install` from the root of the repository
1. Obtain the location of the virtual environment (i.e.: `poetry env list --full-path`)
1. Configure your IDE to use the python interpreter from that location

If your IDE is python-smart, it should be able to pick up all imports automatically, regardless of your PYTHONPATH or your working directory.
Since the local source is linked to, any change to the source code will be reflected on the next run.


# FAQ

## constraints vs locks - where do they apply?

When you call `poetry install`, you end up installing packages based on the `poetry.lock` file.
The resulting packages will always be the same, no matter what.
This is the dev scenario.

When you call `pip install`, you are installing packages based on the constraints placed in a `pyproject.toml` or a `setup.py` file.
Unless the constraints are hard pinned versions, the resulting packages are not guaranteed and will depend on the point in time when the installation is performed, among other factors.
This is the shared library scenario.

When you use poetry, you cover the two scenarios above.

The third scenario is the private business use case: you want to freeze your dependencies in time so that everything from the developer to the CI servers to the production system is identical.
Essentially, you want `poetry install` without the dev requirements.

This functionality is provided out of the box by `stew build`, which creates a pip-installable package from the lock file that you can then stash in a private storage of your choice or pass around your deployments.


## How to provision a production system

### Preparing the virtual environment

You can keep `poetry` and `stew` off your production environment by creating a frozen archive of your application or library from your CI servers (docker used as example):

- Use the `stew build` tool which:
    - performs a `poetry build` on your project
    - calls `pip download` based on the content of the lock file
    - Moves the artifacts to the `.wheels` folder of your repo (can be configured with `--target`)
- Recommended: Use the `--python` switch when calling `stew build` to specify which python executable to use! Make sure to use a python interpreter that matches the os/arch/bits of the system you want to provision
- Include the `.wheels` folder into your Docker build context
- In your Dockerfile:
    - ADD the `.wheels` folder
    - Manage the `pip` version! Either update it to latest, or pin it to something.
    - Prepare a python environment
        - Use `python -m venv <location>` to create a virtual environment natively.
        - Note the executable location... typically (`location/bin/python` or `location/Scripts/python.exe`)
    - Install your application into the python environment you just created:
        - Use `<venv-python-exec> -m pip install <your-package> --no-index --find-links <wheels-folder-location>`
    - You may delete the `.wheels` folder if you want. Consider keeping a copy of the lock file within the docker image, for reference
    

### Using the environment

Using the correct interpreter is all you need to do. There is no activation script or environment variables to set up: the interpreter's executable is a fully bootstrapped and isolated environment.

- A python dockerfile may call `<venv-python-exec>` directly in the dockerfile's CMD
- A service that spawns other processes should receive the path to the `<venv-python-exec>`

[Use the `-m` switch](https://docs.python.org/3/using/cmdline.html#cmdoption-m) in order to launch your app!
