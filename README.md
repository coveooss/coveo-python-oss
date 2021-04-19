# coveo-python-oss

This repository is a collection of useful, general-purpose python libraries
made by Coveo.


## Conventions and rules (aka The Boilerplate™)

A boilerplate is provided in `/coveo-example-library`. Just copy/rename and adjust for profit.
Take the time to read and understand [its readme](./coveo-example-library/README.md) before adding your first project as it contains the rules and conventions used in each project.


## For developers

All projects in this repository are backed by [coveo-stew](./coveo-stew/README.md) and [poetry](https://python-poetry.org/).
A dev environment is provided at `/pyproject.toml` which aggregates all the projects into one convenient virtual environment. 
Refer to poetry's documentation if you're new to poetry.

You can also use each project's individual environment, which has the added benefit of making sure
that all dependencies were correctly declared in the `pyproject.toml` file.
