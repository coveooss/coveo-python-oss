# pyproject

Helps with both the packaging and development sides of python projects backed by poetry.


## Install

We strongly recommend using `pipx` to wrap this into a nice little space:

```
pip install pipx --user
pipx install coveo-pyproject --index-url https://pypi.dev.cloud.coveo.com/simple
```

## Commands

`pyproject <command>`

The `pyproject` entrypoint has a bunch of commands designed to interact with `pyproject.toml` and `poetry`.

It's designed to simplify common operations over multiple sub projects.

Some commands can target "all" projects in a repository. What "all" means will depend on your context:
- Within a git repository, "all" means everything from the first git parent.
- Outside of the git context, "all" is the current directory, recursive.

### build some-project
This command outputs the artifacts of your project into a folder, so that it can be distributed based on its `poetry.lock`
metadata.

This is different from publishing to a `pypi` server, where distribution is based on the _constraints_ you placed
in `pyproject.toml`.

A nice bonus is that the folder does not require poetry or coveo-pyproject to be installed, so it helps keeping production
systems as small and specific as they should be.

To install from the artifacts folder: 
`pip install --no-index --find-links /path/to/.wheels <package-name>`

Without a project name specified, all projects will be built.

Scroll down to the poetry gotchas for a more detailed use case and why this command exists!


### check-outdated
Ensure that all files in the repo are up to date and return an error if something's outdated.

A file is out of date if:
- the `pyproject.toml` changed but not the `poetry.lock`
- a `pydev` project's dev requirements changed and `pull-dev-requirements` was not called.


### fix-outdated
Like `pyproject check-outdated`, but also fixes anything that is outdated.


### bump some-project
Bumps the version of all dependencies of _some-project_.

Without a project specified, all lock files of the repository will be updated. This doesn't update constraints, rather, it
bumps everything to the latest version that match your constraints.


### pull-dev-requirements
`poetry install` will not install the dev-requirements of dependencies...

If you have a `pyproject.toml` that is aimed at unifying all python projects of a 
repository inside a single environment, run this script to pull the dev requirements
of local dependencies inside that file.

To mark such a development-only environment, add this to its `pyproject.toml` file:

```
[tool.coveo.pyproject]
pydev = true
```

Note: pydev projects cannot (and should not) be built or published.


### fresh-eggs
This will remove all `*.egg-info` and rebuild them.

The `egg-info` is used by poetry to link all local dependencies correctly in the virtual environment.
Some changes to `pyproject.toml` will not be reapplied on `poetry install` unless you delete the egg.

For example, changing something in the `[tool.poetry.script]` section requires fresh-eggs.

Use `fresh-eggs` as a last resort, try with `poetry install` first.


# poetry gotchas

## pip knows about poetry

Did you know? You can `pip install` from a folder with `pyproject.toml` without having poetry installed on your system! Be careful though as this method will not activate any virtual environment.

Reference: https://pip.pypa.io/en/stable/reference/pip/#pep-517-and-518-support

## constraints vs locks - where do they apply?

Poetry locks down the dependencies of your project for development use (the lock file). Its only use is to
prepare python virtual environments.

But when published, it's the `pyproject.toml` that gets uploaded to the artifactory, not the lock file! This is necessary so that your package can be installed alongside other packages without too much conflicts.

- Shared libraries should keep the loosest constraint you can afford in order to maximize compatibility.
- Applications, services, tests can use more specific constraints, if necessary.

## not so great: trick poetry into provisioning your production system

For a private production server with our own python libraries, we want to install what's in the lock file, not what's in the toml file. Poetry offers us two options here:  

- You can use `poetry config` and disable the virtual environment. When calling `poetry install`, the system's python libraries will be synchronized with the lock file.
- You can mimic the development flow, and use `poetry install` and `poetry run` to run your application in production.

Both options require poetry to be installed at some point on the production system to work. This may
require your build system (e.g.: Docker) to be VPN-aware which is known to require tweaks to work properly.
An easier method is outlined in "how to provision a production system" down below! :)


# How to depend on libraries...

## ...from pypi.dev 

First you need to add the repository metadata to your `pyproject.toml` file:

```
[[tool.poetry.source]]
name = "pypi.dev"
url = "https://pypi.dev.cloud.coveo.com/simple/"
default = true
```

> The `default=true` is necessary to circumvent an issue with pip and poetry. Not using it may create problems for other projects that depends on your project.

Then, specify the source when declaring the dependency in `pyproject.toml`:

```
[tool.poetry.dependencies]
cdf-clients = { version = "^2.4", source = "pypi.dev" }
```

The next `poetry lock` will adjust the `poetry.lock` file with this information.


## ...from local paths published to pypi.dev

Poetry offers a `path` constraint that you can use to reference local libraries:

```
[tool.poetry.dependencies]
cdf-clients = { version = "^2.4", source = "pypi.dev" }

[tool.poetry.dev-dependencies]
cdf-clients = { path = "../cdf-clients/" }
```

It's important to keep local paths in the `dev-dependencies` section if you are publishing your project. If you don't,
the constraint will not be published to pypi correctly and:

- It will install the latest version available during a vanilla install (instead of your constraint)
- It will not be upgraded during a `pip install --update` call; since the dependency is already installed and it fulfills
the (absence of) constraint, poetry favors the pre-installed package over an upgrade.


## ...from local paths not published to pypi.dev

Just link it in the dependencies directly and drop the constraint:

```
[tool.poetry.dependencies]
cdf-clients = { path = "../cdf-clients/" }
```

Limitation: You cannot publish to `pypi.dev` if you use unpublished libraries in `tool.poetry.dependencies`.
However, you can still use `pyproject build` to create a package that will include all of the dependencies, including the unpublished local paths, and install it "offline".

To work around this limitation, Poetry provides a `packages` section that may be used to bundle additional files when publishing.


# How to create a python development environment

This special kind of project cannot (and should not) be built or published. It's only a convenience tool for developers.

I use a `pyproject.toml` file in the root of my repository, which serves the purpose of a python environment that contains
all of the in-tree python projects inside my repository:

```
[tool.poetry]
name = "devtools-pydev"
version = "0.0.1"
description = "Development environment for devtool's python components."
authors = ["Jonathan piché <jpiche@coveo.com>"]


[tool.poetry.dependencies]
python = ">=3.6"
coveo-grab-bag = { path = "coveo-grab-bag/", extras = ["all"] }
coveo-pypi-cli = { path = "coveo-pypi-cli/" }
coveo-pyproject = { path = "coveo-pyproject/" }


[tool.poetry.dev-dependencies] # pydev projects' dev-dependencies are autogenerated; do not edit manually!
mypy = "*"
pytest = "*"
requests-mock = "*"


[tool.coveo.pyproject]
pydev = true
```

You may notice a new section here called `[tool.coveo.pyproject]` - we use it to add coveo-specific metadata.

The `pydev = true` option is covered in the `pyproject pull-dev-requirements` command described above. For now, it's a quick way of
obtaining the dev dependencies of your in-tree dependencies.
This is necessary because:
- Poetry does not install the dev dependencies of dependencies, regardless if they're local or not.
- The locked versions in your pydev project may become out of sync with the locked versions of the local projects.


# How to provision a production system

## Installing a project

You can keep `poetry` and `coveo-pyproject` off your production environment by creating an offline install of your application or library:

- Use the `pyproject build` tool which:
    - performs a `poetry build` on your project
    - calls `pip download` based on the content of the lock file
    - Moves the artifacts to the `.wheels` folder of your repo (can be configured with `--target`)
- Recommended: Use the `--python` switch to specify which python executable to use! Make sure to use a python interpreter that matches the os/arch/bits of the system you want to provision.
- Include the `.wheels` folder into your Docker build context
- In your Dockerfile:
    - ADD the `.wheels` folder
    - Manage the `pip` version! Either update it to latest, or pin it to something.
    - Prepare a python environment
        - Use `python -m venv <location>` to create a virtual environment natively.
        - Note the executable location... typically (`location/bin/python` or `location/Scripts/python.exe`)
    - Install your application into the python environment you just created:
        - Use `<venv-python-exec> -m pip install <your-package> --no-index --find-links <wheels-folder-location>`
    - You may delete the `.wheels` folder if you want. Consider keeping a copy of the lock file within the docker image, for reference.


## Activating the environment for a process

Using the correct interpreter is all you need to do. There is no activation script or environment variables to set up: the executable
is already a fully bootstrapped isolated environment.

A python service will use the `<venv-python-exec>` directly in its CMD.

A service that spawns python processes will need to find a way to retrieve the `<venv-python-exec>`. This is most easily done
through a custom environment variable. Some like to manipulate the PATH variable for this but keep in mind that your OS may rely on packages that are not available in your virtual environment.

If you're a python service that spawns python processes, the active interpreter path can be retrieved at runtime using `sys.executable`.


# https://pypi.dev.cloud.coveo.com

## Publishing

Using `poetry version`, bump/commit the version you want to publish into the `pyproject.toml` file.

The jenkins script should (pseudo-code):
```
# Configure the target repository in poetry's config
poetry config repositories.pypi.dev https://pypi.dev.cloud.coveo.com/simple

# Configure the credentials for the repository (a usernamePassword credentials in jenkins named "pypi-dev")
withCredentials([usernamePassword(
  credentialsId: 'pypi-dev',
  passwordVariable: 'PYPI_DEV_PASSWORD',
  usernameVariable: 'PYPI_DEV_USERNAME')])
{ poetry config http-basic.pypi.dev $PYPI_DEV_USERNAME $PYPI_DEV_PASSWORD }

# build it
poetry build --format wheel

# push it
poetry publish --repository pypi.dev --no-interaction
```

Note: Poetry will not verify if the version exists and will gladly update (overwrite) an existing version.


## Better Publishing :sweat_smile:

[This jenkins file](https://github.com/coveo/core_pipeline/src/master/jenkinsfiles/pypi.groovy) does a lot of fun things:

- It can target any project with a pyproject.toml file, from any repository.
- It prevents you from overwriting an existing version.
- It automatically computes and sets the version to publish.
- It can publish pre-release versions too, great for testing branches.
- It can be told to skip publishing if no changes are detected, so there are no extra versions.
- It can tag your repository so you can quickly locate the changeset of any given version.

If you're on the `corebuilds` jenkins server, the `pypi(...)` groovy command from core_pipeline handles calling [this job](https://corebuilds.dev.cloud.coveo.com/view/Python/job/pypi/) automatically.

If you haven't done so already, you can import core_pipeline like this:
```
library(identifier: 'core_pipeline@v2.34',
    retriever: modernSCM(github(
        credentialsId: "github-app-dev",
        repository: "core_pipeline",
        repoOwner: "coveo"
    )),
    changelog: false
)
```

If you're on another server, it's probably better off to copy the jenkinsfile and adapt it to your needs to reduce coupling as much as possible.
