# coveo-testing

A set of test/pytest helpers to facilitate common routines.


Content in a nutshell:

- Reusable pytest markers (UnitTest, IntegrationTest)
- Unique ID generation for tests
- Multiline logging assertions with includes, excludes, levels and comprehensive assertion output
- Refactorable `unittest.mock.patch('this.module')` module references

- Human-readable (but still customizable) display for parametrized tests


This project is used as the test base for all other projects in this repository.

Therefore, it cannot depend on any of them.

More complex use cases may be implemented in the `coveo-testing-extras` project. That's also where you can depend on projects that depend on `coveo-testing`. 


# pytest markers and auto-registration

This enables code completion on markers.

Three markers are already provided: `[UnitTest, Integration, Interactive]`

Here's how you can create additional markers:

```python
# /test_some_module/markers.py
import pytest

DockerTest = pytest.mark.docker_test
CloudTest = pytest.mark.cloud_test

ALL_MARKERS = [DockerTest, CloudTest]
```

You can then import these markers and decorate your test functions accordingly:

```python
# /test_some_module/test_something.py
from coveo_testing.markers import UnitTest, Integration, Interactive
from test_some_module.markers import CloudTest, DockerTest

@UnitTest
def test_unit() -> None:
    ...  # designed to be fast and lightweight, most likely parametrized


@Integration
def test_integration() -> None:
    ...  # combines multiple features to achieve a test


@CloudTest
def test_in_the_cloud() -> None:
    ...  # this could be a post-deployment test, for instance.


@DockerTest
@Integration
def test_through_docker() -> None:
    ... # will run whenever docker tests or integration tests are requested


@Interactive
def test_interactive() -> None:
    ...  # these tests rely on eye-validations, special developer setups, etc  

```

Pytest will issue a warning when markers are not registered.

To register coveo-testing's markers along with your custom markers, use the provided `register_markers` method:

```python
# /test_some_module/conftest.py
from _pytest.config import Config
from coveo_testing.markers import register_markers
from test_some_module.markers import ALL_MARKERS

def pytest_configure(config: Config) -> None:
    """This pytest hook is ran once, before collecting tests."""
    register_markers(config, *ALL_MARKERS)
```


# Human-readable unique ID generation

The generated ID has this format:

`friendly-name.timestamp.pid.host.executor.sequence`

- friendly-name:
  - provided by you, for your own benefit
    
- timestamp: 
  - format "%m%d%H%M%S" (month, day, hour, minutes, seconds)
  - computed once, when TestId is imported
    
- pid:
  - the pid of the python process
    
- host:
  - the network name of the machine

- executor:
  - the content of the `EXECUTOR_NUMBER` environment variable
  - returns 'default' when not defined  
  - historically, this variable comes from jenkins
  - conceptually, it can be used to help distribute (and identify) tests and executors

- sequence:
  - Thread-safe
  - Each `friendly-name` has an isolated `sequence` that starts at 0
  - Incremented on each new instance
  - Enables support for parallel parametrized tests

```python
from coveo_testing.temporary_resource.unique_id import TestId, unique_test_id


# the friendly name is the only thing you need to specify
test_id = TestId('friendly-name')
str(test_id)
'friendly-name.0202152243.18836.WORKSTATION.default.0'


# you can pass the instance around to share the ID
str(test_id)
'friendly-name.0202152243.18836.WORKSTATION.default.0'


# create new instances to increment the sequence number
test_id = TestId('friendly-name')
str(test_id)
'friendly-name.0202152243.18836.WORKSTATION.default.1'


# use it in parallel parameterized tests
import pytest

@pytest.mark.parametrize('param', (True, False))
def test_param(param: bool, unique_test_id: TestId) -> None:
    # in this case, the friendly name is the function name and
    # the sequence will increase on each parameter
    # test_param.0202152243.18836.WORKSTATION.default.0
    # test_param.0202152243.18836.WORKSTATION.default.1
    ...
```


# multiline logging assertions

Maybe pytest's `caplog` is enough for your needs, or maybe you need more options.
This tool uses `in` and `not in` to match strings in a case-sensitive way.

```python
import logging
from coveo_testing.logging import assert_logging

with assert_logging(
        logging.getLogger('logger-name'),
        present=['evidence1', 'evidence2'], 
        absent=[...], 
        level=logging.WARN):
    ...
```


# Human-readable (but still customizable) display for parametrized tests

If you're like me, you typed `@pytest.mark.parametrize` wrong a couple of times!

Enable IDE completion by using this one instead:

```python
from coveo_testing.parametrize import parametrize

@parametrize('var', (True, False))
def test_var(var: bool) -> None:
    ...
```

It has one difference vs the pytest one, and it's the way it formats the "parameter name" for each iteration of the test.

Pytest will skip a lot of types and will simply name your test "var0", "var1" and so on.
Using this `@parametrize` instead, the variable's content will be inspected:

```python
from typing import Any
from coveo_testing.parametrize import parametrize
import pytest


class StrMe:
  def __init__(self, var: Any) -> None:
    self.var = var
      
  def __str__(self) -> str:
    return f"Value: {self.var}"


@parametrize('var', [['list', 'display'], [StrMe('hello')]])
def test_param(var: bool) -> None:
    ...

@pytest.mark.parametrize('var', [['list', 'display'], [StrMe('hello')]])
def test_param_from_pytest(var: bool) -> None:
    ...
```

If you run `pytest --collect-only` you will obtain the following:
```
    <Function test_param[list-display]>
    <Function test_param[Value: hello]>
    <Function test_param_from_pytest[var0]>
    <Function test_param_from_pytest[var1]>
```
