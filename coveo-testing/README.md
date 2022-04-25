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

More complex use cases may be implemented in the `coveo-testing-extras` project. 
That's also where you can depend on projects that depend on `coveo-testing`. 


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


# Refactorable mock targets

## Demo

Consider this common piece of code:

```python
from unittest.mock import patch, MagicMock

@patch("mymodule.clients.APIClient._do_request")
def test(api_client_mock: MagicMock) -> None:
    ...
```

Because the mock target is a string, it makes it difficult to move things around without breaking the tests. You need a
tool that can extract the string representation of a python objet. This is what `ref` was built for:

```python
from unittest.mock import patch, MagicMock
from coveo_testing.mocks import ref
from mymodule.clients import APIClient

@patch(*ref(APIClient._do_request))
def test(api_client_mock: MagicMock) -> None:
    ...
```

🚀 This way, you can rename or move `mymodule`, `clients`, `APIClient` or even `_do_request`, and your IDE should find
these and adjust them just like any other reference in your project.

Let's examine a more complex example:

```python
from unittest.mock import patch, MagicMock
from mymodule.tasks import process

@patch("mymodule.tasks.get_api_client")
def test(get_api_client_mock: MagicMock) -> None:
    assert process() is None  # pretend this tests the process function
```

The interesting thing in this example is that we're mocking `get_api_client` in the `tasks` module. 
Let's take a look at the `tasks` module:

```python
from typing import Optional
from mymodule.clients import get_api_client

def process() -> Optional[bool]:
    client = get_api_client()
    return ...
```

As we can see, `get_api_client` is defined in another module.
The test needs to patch the function _in the tasks module_ since that's the context it will be called from. 
Unfortunately, inspecting `get_api_client` from the `tasks` module at runtime leads us back to `mymodule.clients`.

This single complexity means that hardcoding the context `mymodule.tasks` and symbol `get_api_client` into a string
for the patch is the straightforward solution.

But with `ref`, you specify the context separately:

```python
from unittest.mock import patch, MagicMock
from coveo_testing.mocks import ref
from mymodule.clients import get_api_client
from mymodule.tasks import process


@patch(*ref(get_api_client, context=process))
def test(get_api_client_mock: MagicMock) -> None:
    assert process() is None  # pretend this tests the process function
```

🚀 By giving a context to `ref`, the symbol `get_api_client` will be resolved from the context of `process`, which is the
`mymodule.tasks` module. The result is `mymodule.tasks.get_api_client`.

If either objects (`get_api_client` or `process`) are moved or renamed using a refactoring tool, the mock will still
point to the correct name and context.

🚀 And a nice bonus is that your IDE can jump to `get_api_client`'s definition from the test file now!

It should be noted that this isn't just some string manipulation. `ref` will import and inspect modules and objects
to make sure that they're correct. Here's a more complex case with a renamed symbol:

The module:

```python
from typing import Optional
from mymodule.clients import get_api_client as client_factory  # it got renamed! 😱

def process() -> Optional[bool]:
    client = client_factory()
    return ...
```

The test:

```python
from unittest.mock import patch, MagicMock
from coveo_testing.mocks import ref
from mymodule.clients import get_api_client
from mymodule.tasks import process


@patch(*ref(get_api_client, context=process))
def test(get_api_client_mock: MagicMock) -> None:
    assert process() is None  # pretend this tests the process function
```

Notice how the test and patch did not change despite the renamed symbol?

🚀 This is because `ref` will find `get_api_client` as `client_factory` when inspecting `mymodule.tasks` module,
and return `mymodule.tasks.client_factory`.

We can also use ref with `patch.object()` in order to patch a single instance. Consider the following code:

```python
from unittest.mock import patch
from mymodule.clients import APIClient

def test() -> None:
    client = APIClient()
    with patch.object(client, "_do_request"):
        ...
```

🚀 By specifying `obj=True` to `ref`, you will obtain a `Tuple[instance, attribute_to_patch_as_a_string]` that you
can unpack to `patch.object()`:

```python
from unittest.mock import patch
from coveo_testing.mocks import ref
from mymodule.clients import APIClient

def test() -> None:
    client = APIClient()
    with patch.object(*ref(client._do_request, obj=True)):
        ...
```

Please refer to the docstring of `ref` for argument usage information.

## Common Mock Recipes

### Mock something globally without context
#### Option 1: by leveraging the import mechanism

To mock something globally without regards for the context, it has to be accessed through a dot `.` by the context.

For instance, consider this test:

```python
from http.client import HTTPResponse
from unittest.mock import patch, MagicMock
from coveo_testing.mocks import ref

from mymodule.tasks import process


@patch(*ref(HTTPResponse.close))
def test(http_response_close_mock: MagicMock) -> None:
    assert process()
```

The target is `HTTPResponse.close`, which lives in the `http.client` module.
The contextof the test is the `process` function, which lives in the `mymodule.tasks` module.
Let's take a look at `mymodule.tasks`'s source code:


```python
from http import client

def process() -> bool:
    _ = client.HTTPResponse(...)  # of course this is fake, but serves the example
    return ...
```

Since `mymodule.tasks` reaches `HTTPResponse` through a dot (i.e.: `client.HTTPResponse`), we can patch `HTTPResponse`
without using `mymodule.tasks` as the context.

However, if `mymodule.tasks` was written like this:

```python
from http.client import HTTPResponse

def process() -> bool:
    _ = HTTPResponse(...)
    return ...
```

Then the patch would not affect the object used by the `process` function anymore. However, it would affect any other 
module that uses the dot to reach `HTTPResponse` since the patch was _still_ applied globally.
 

#### Option 2: By wrapping a hidden function

Another approach to mocking things globally is to hide a function behind another, and mock the hidden function.
This allows modules to use whatever import style they want, and the mocks become straightforward to setup.

Pretend this is `mymodule.clients`:

```python
class APIClient:
    ...

def get_api_client() -> APIClient:
    return _get_api_client()

def _get_api_client() -> APIClient:
    return APIClient()
```

And this is `mymodule.tasks`:

```python
from mymodule.clients import get_api_client

def process() -> bool:
    return get_api_client() is not None
```

So you _know_ this works globally, because no one will (should?) import the private one except the test:

```python
from unittest.mock import patch, MagicMock
from coveo_testing.mocks import ref

from mymodule.tasks import process
from mymodule.clients import _get_api_client


@patch(*ref(_get_api_client))
def test(api_client_mock: MagicMock) -> None:
    assert process()
```


### Mock something for a given context

When you want to mock something for a given module, you must provide a hint to `ref` as the `context` argument.

The hint may be a module, or a function/class defined within that module. "Defined" here means that "def" or "class" 
was used _in that module_. If the hint was imported into the module, it will not work:

`mymodule.tasks`:

```python
from mymodule.clients import get_api_client

def process() -> bool:
    client = get_api_client()
    return ...
```

The test, showing 3 different methods that work:

```python
from unittest.mock import patch, MagicMock
from coveo_testing.mocks import ref

from mymodule.clients import get_api_client
from mymodule.tasks import process

# you can pass the module as the context
import mymodule

@patch(*ref(get_api_client, context=mymodule.tasks))
def test(get_api_client_mock: MagicMock) -> None:
    assert process()

# you can pass the module as the context, version 2
from mymodule import tasks
    
@patch(*ref(get_api_client, context=tasks))
def test(get_api_client_mock: MagicMock) -> None:
    assert process()

# you can also pass a function or a class defined in the `tasks` module
from mymodule.tasks import process
@patch(*ref(get_api_client, context=process))
def test(get_api_client_mock: MagicMock) -> None:
    assert process()
```

The 3rd method is encouraged: provide the function or class that is actually using the `get_api_client` import.
In our example, that's the `process` function.
If `process` was ever moved to a different module, it would carry the `get_api_client` import, and the mock would
be automatically adjusted to target `process`'s new module without changes.

### Mock something for the current context

Sometimes, the test file _is_ the context. When that happens, just pass `__name__` as the context:

```python
from unittest.mock import patch
from coveo_testing.mocks import ref
from mymodule.clients import get_api_client, APIClient

def _prepare_test() -> APIClient:
    client = get_api_client()
    ...
    return client
    
@patch(*ref(get_api_client, context=__name__))
def test() -> None:
    client = _prepare_test()
    ...
```


### Mock a method on a class

Since a method cannot be imported and can only be accessed through the use of a dot `.` on a class or instance, 
you can always patch methods globally:

```python
with patch(*ref(MyClass.fn)): ...
```

This is because no module can import `fn`; it has to go through an import of `MyClass`.

### Mock a method on one instance of a class

Simply add `obj=True` and use `patch.object()`:

```python
with patch.object(*ref(instance.fn, obj=True)): ...
```


### Mock an attribute on a class/instance/module/function/object/etc

`ref` cannot help with this task:
- You cannot refer an attribute that exists (you would pass the value, not a reference)
- You cannot refer an attribute that doesn't exist (because it doesn't exist!)

For this, there's no going around hardcoding the attribute name in a string:

```python
class MyClass:
    def __init__(self) -> None:
        self.a = 1


def test_attr() -> None:
    instance = MyClass()
    with patch.object(instance, "a", new=2):
        assert instance.a == 2
        assert MyClass().a == 1
```

This sometimes work when patching **instances**. 
The example works because `a` is a simple attribute that lives in `instance.__dict__` and `patch.object` knows
about that.

But if you tried to patch `MyClass` instead of `instance`, `mock.patch` would complain that there's no 
such thing as `a` over there.
Thus, patching an attribute globally will most likely result in a lot of wasted time, and should be avoided.

There's no way to make the example work with `ref` because there's no way to refer `instance.a` without actually
getting the value of `a`, unless we hardcode a string, which defeats the purpose of `ref` completely.


### Mock a property

You can only patch a property globally, through its class:

```python
class MyClass:
    @property
    def get(self) -> bool:
        return False
```

```python
from unittest.mock import PropertyMock, patch, MagicMock
from coveo_testing.mocks import ref

from mymodule import MyClass

@patch(*ref(MyClass.get), new_callable=PropertyMock, return_value=True)
def test(my_class_get_mock: MagicMock) -> None:
    assert MyClass().get == True
    my_class_get_mock.assert_called_once()
```

You **cannot** patch a property on an instance, this is a limitation of `unittest.mock` because of the way
properties work.
If you try, `mock.patch.object()` will complain that the property is read only.


### Mock a classmethod or staticmethod on a specific instance

When inspecting these special methods on an instance, `ref` ends up finding the class instead of the instance.

Therefore, `ref` is unable to return a `Tuple[instance, function_name]`.
It would return `Tuple[class, function_name]`, resulting in a global patch. 😱

But `ref` will detect this mistake, and will raise a helpful exception if it cannot return an instance when you
specified `obj=True`.

For this particular scenario, the workaround is to provide the instance as the context:

```python
from unittest.mock import patch
from coveo_testing.mocks import ref


class MyClass:
    @staticmethod
    def get() -> bool:
        return False

    
def test() -> None:
    instance = MyClass()
    with patch.object(*ref(instance.get, context=instance, obj=True)) as fn_mock:
        assert instance.get == True
        assert MyClass().get == False  # new instances are not affected by the object mock
        fn_mock.assert_called_once()
```

Some may prefer a more semantically-correct version by specifying the target through the class instead of the 
instance. In the end, these are all equivalent:

```python
with patch.object(instance, "get"): 
    ...

with patch.object(*ref(instance.get, context=instance, obj=True)): 
    ...

with patch.object(*ref(MockClass.get, context=instance, obj=True)): 
    ...
```

In this case, the version without ref is much shorter and arguably more pleasant for the eye, but `get` can no longer
be renamed without altering the tests.
