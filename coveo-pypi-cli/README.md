# coveo-pypi-cli

A very simple pypi cli that can be used to obtain the latest version of a package, or calculate the next one.

Serves our automatic pypi push github action.


## `pypi current-version`

Display the current version of a package from `pypi.org`


## `pypi next-version`

Compute the next version of a package.

- Can be given a minimum version
  - e.g.: pypi is `0.0.3` and mininum set to `0.1`: next version will be `0.1`
- Supports computing pre-release versions

# private index support

You can target a private pypi server through a switch or an environment variable.

## Using the `--index` switch

```shell
$ pypi current-version secret-package --index https://my.pypi.server.org
1.0.0

$ pypi current-version secret-package --index https://my.pypi.server.org:51800/urlprefix
1.0.0
```

## Using the environment variable:

```shell
$ PYPI_CLI_INDEX="https://my.pypi.server.org" pypi current-version secret-package
```

Note: Unlike `pip --index-url`, **you must omit** the `/simple` url prefix.
The API used by `coveo-pypi-cli` is served by the `/pypi` endpoint _and should not be specified either!_


# pypi-cli in action

The best example comes from the [github action](./.github/workflows/actions/publish-to-pypi), which computes the next version based on the current release and what's in the `pyproject.toml`.

Here's what you can expect from the tool:

```shell
$ pypi current-version coveo-functools
0.2.1

$ pypi next-version coveo-functools
0.2.2

$ pypi next-version coveo-functools --prerelease
0.2.2a1

$ pypi next-version coveo-functools --minimum-version 0.2
0.2.2

$ pypi next-version coveo-functools --minimum-version 0.3
0.3

$ pypi next-version coveo-functools --minimum-version 0.3 --prerelease
0.3a1


# Here's an example of how we use it in the github action

$ poetry version
coveo-pypi-cli 0.1.0
$ minimum_version=$(poetry version | cut --fields 2 --delimiter ' ' )
0.1.0

# when left unattended, the next-version increments the patch number
$ pypi next-version coveo-pypi-cli --minimum-version $minimum_version
0.2.2

# in order to change the minor or major, because the script uses `poetry version` to obtain the minimum version, 
# just set it in `pyproject.toml` manually or by calling `poetry version <new-version>` (and commit!)
$ poetry version 0.3
Bumping version from 0.1.0 to 0.3
$ minimum_version=$(poetry version | cut --fields 2 --delimiter ' ' )
0.3
$ pypi next-version coveo-pypi-cli --minimum-version $minimum_version
0.3

# IMPORTANT: the publish step MUST set the computed version for poetry before publishing!
$ poetry version $minimum_version
0.3
$ poetry publish
...

# after publishing the above, repeating the steps would yield:
$ pypi next-version coveo-pypi-cli --minimum-version $minimum_version
0.3.1

# for completeness, you can also publish pre-releases:
$ pypi next-version coveo-pypi-cli --minimum-version $minimum_version --prerelease
0.3.1a1

 
```
