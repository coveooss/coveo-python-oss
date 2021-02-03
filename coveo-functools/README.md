# coveo-functools

Introspection, finalizers, delegates, dispatchers, waiters...
These utilities aim at increasing productivity.


## annotation

Introspect classes and callables at runtime.

Can convert string annotations into their actual type reference.


## casing / flexcase

Flexcase takes a "dirty" input and maps it to a python construct.

The principal use case is to allow seamless translation between snake_case and camelCase and generate PEP8-compliant code over APIs that support a different casing scheme.

- It introspects a function to obtain the expected argument names
- It inspects the provided input to find matching candidates
- It calls the function with the cleaned arguments

It can also be used to allow for a certain degree of personalization in typically strict contexts such as configuration files and APIs. 

Take for example the toml below, where all 3 items are equivalent:

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
