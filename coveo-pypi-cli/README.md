# coveo-pypi-cli

A very simply pypi cli that can be used to obtain the latest version of a package, or calculate the next one.

Serves our automatic pypi push github action.


## `pypi current-version`

Display the current version of a package from `pypi.org`


## `pypi next-version`

Compute the next version of a package.

- Can be given a minimum version
  - e.g.: pypi is `0.0.3` and mininum set to `0.1`: next version will be `0.1`
- Supports computing pre-release versions
