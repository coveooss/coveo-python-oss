# coveo-functools

Introspection, finalizers, delegates, dispatchers, waiters...
These utilities aim at increasing productivity!


## annotations

Introspect classes and callables at runtime.

Can convert string annotations into their actual type reference.


## flex

Flex takes a "dirty" input and maps it to a python construct.

The principal use case is to allow seamless translation between snake_case and camelCase and generate PEP8-compliant code over APIs that support a different casing scheme.

- It introspects a function/class to obtain the expected argument names
- It inspects the provided input to find matching candidates
- It calls the function with the cleaned arguments
- It can recurse into nested custom types based on annotations
- It strips out the data you don't need from the payload

It can also be used to allow for a certain degree of personalization in typically strict contexts such as configuration files and APIs. 

Take for example the toml below, where all 3 items can be made equivalent:

```toml
[tool.some-plugin]
enable_features = ['this', 'that']
enable-features = ['this', 'that']
enableFeatures = ['this', 'that']
```

Or maybe in a CLI app, to allow both underscores and dashes:

```shell
# which one was it?
poetry install --no-dev
poetry install --no_dev
```

### @flex

This decorator will wrap a class, method or function so that it can be called with flexible arguments:

```python
from coveo_functools.flex import flex

PAYLOAD = {"TEST": "SUCCESS"}

@flex
class FlexibleConstructor:
    def __init__(self, test: str) -> None:
        self.test = test

    @flex
    def flexible_method(self, test: str) -> str:
        return test


@flex
def flexible_function(test: str) -> str:
    return test

instance = FlexibleConstructor(**PAYLOAD)

assert instance.test == "SUCCESS"
assert instance.flexible_method(**PAYLOAD) == "SUCCESS"
assert flexible_function(**PAYLOAD) == "SUCCESS"


# you can also use the tool inline; for instance to wrap a 3rd party lib:
def typical_function(test: str) -> str:
    return test

assert flex(typical_function)(**PAYLOAD) == "SUCCESS"
```

Let's see a more practical example:

```python
from dataclasses import dataclass

import requests  # noqa
from coveo_functools.flex import flex


@dataclass
class Owner:
    login: str


@flex
@dataclass
class ApiResponse:
    id: int
    owner: Owner

# Consider this api response:
# {
#     "Id": 1234,
#     "Owner": {"login": "jonapich"},
#     "Url": "https://..."
# }
response = ApiResponse(**requests.get(...).json)
assert response.owner.login == 'jonapich'
```

In the example above, notice how Owner doesn't have to be decorated?
This is because @flex works recursively on any type.
You can decorate it too, but the first call is what matters.

#### consideration vs mypy

There is one annotation case worth mentioning. 
Consider this code:

```python
class Inner:
    ...

@flex
def fn(inner: Inner) -> ...:
    ...

_ = fn(**{'inner': {...}})
```

In this case, mypy will infer that you're doing `**Dict[str, Dict]`
and complain that Dict is not compatible with Inner.

To solve this without an ignore statement, 
explicitly annotate/cast your payloads with Any:

```python
payload: Dict[str, Any] = {"inner": {}}
_ = fn(**payload)
```

### unflex

Unflex is one of the utilities used by the @flex decorator.

It can remap a dictionary to fit the keyword arguments (casing/etc) given by a callable:

```python
from coveo_functools.flex import unflex

def fn(arg1: str, arg2: str) -> None:
    ...

assert unflex(fn, {"ARG1": ..., "ArG_2": ...}) == {"arg1": ..., "arg2": ...}
```

### @flexcase

`flexcase` is a simpler version of the flex decorator.
It allows a function to apply the `unflex` logic automatically against a callable.

Unlike the flex decorator, it is not recursive and it will
not attempt to read type annotations or convert values.


```python
from coveo_functools.flex import flexcase

@flexcase
def fn(arg1: str, arg2: str) -> str:
    return f"{arg1} {arg2}"


assert fn(ARG1="hello", _arg2="world") == "hello world"
```


## dispatch

An enhanced version of [functools.singledispatch](https://docs.python.org/3.8/library/functools.html#functools.singledispatch):


- Adds support for `Type[]` annotations (singledispatch only works on instances)
- You are no longer limited to the first argument of the method
- You can target an argument by its name too, regardless of its position


## finalizer

A classic and simple try/finally context manager that launches a delegate once a block of code has completed.

A common trick is to "cook" the finalizer arguments through a mutable type such as a list or dict:

```python
from typing import List
from coveo_functools.finalizer import finalizer

def clean_up(container_names: List[str]) -> None:
    for _ in container_names:
        ...
    
def test_spawning_containers() -> None:
    containers: List[str] = []
    with finalizer(clean_up, containers):
        containers.append('some-container-1')
        containers.append('some-container-2')
        containers.append('some-container-3')
```


## wait.until()

Waits for a condition to happen. Can be configured with exceptions to ignore.

```python
from coveo_functools import wait
import requests

def _ready() -> bool:
    return requests.get('/ping').status_code == 200

wait.until(_ready, timeout_s=30, retry_ms=100, handle_exceptions=ConnectionError,
           failure_message="The service failed to respond in time.")
```

## wait.Backoff

A customizable class to assist in the creation of backoff retry strategies.

- Customizable growth factor
- Jitter
- Backoff progress % (want to fire some preliminary alarms at 50% backoff maybe?)
- Supports infinite backoff
- Can be configured to raise after too many attempts
- Can be configured to raise after a set amount of time

e.g.: Worker loop failure management by catching RetriesExhausted

```python
from coveo_functools.wait import Backoff

backoff = Backoff()
while my_loop:
    try:
        do_stuff()
    except Exception as exception:
        try:
            quit_flag.wait(next(backoff))
        except backoff.RetriesExhausted:
            raise exception
```

e.g.: Worker loop failure management without the nested try/catch:

```python
from coveo_functools.wait import Backoff

backoff = Backoff()
while my_loop:
    try:
        do_stuff()
    except Exception as exception:
        wait_time = next(backoff, None)
        if wait_time is None:
            raise exception
        quit_flag.wait(wait_time)
```

e.g.: You can generate the wait times without creating a Backoff instance, too:

```python
import time
from coveo_functools.wait import Backoff

wait_times = list(Backoff.generate_backoff_stages(first_wait, growth, max_backoff))
for sleep_time in wait_times:
    try:
        do_stuff()
        break
    except:
        time.sleep(sleep_time)
else:
    raise ImSickOfTrying()
```
