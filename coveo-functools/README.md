# `coveo-functools`

Introspection, finalizers, delegates, dispatchers, waiters...
These utilities aim at increasing productivity.


# `annotations`

Introspect classes and callables at runtime.

Can convert string annotations into their actual type reference.


# `flex`
## Overview
Flex works with annotations to adjust and convert input data to match your target structure.

It was originally done as a mean to fit `CamelCase` payloads from external APIs into `snake_case` classes.

Take for example this payload that we'd like to fit into a pep8 context:

```json
[
    {"Name": "John", "SocialNumber": 123},
    {"Name": "Jean", "SocialNumber": 123}
]
```

Explicit usage example:

```python
from coveo_functools import flex

@dataclass
class Person:
    name: str
    social_number: Optional[int] = None

# the deserializer is used directly to receive a list of Person instances
response = flex.deserialize(json.load(), hint=List[Person])
```

Automatic usage example:

```python
from coveo_functools.flex import flex

@flex
@dataclass
class SomeObject:
    """ I am decorated with @flex, so you can always give me some trouble. """
    name: str

response = [SomeObject(**data) for data in json.load()]
```

When remapping keys, Flex will ignore:
- Casing
- Underscores
- Hyphens
- Dots
- Spaces

For instance, it will happily accept `{"__NaM e._": "John"}` as valid input for the `Person` class.

It can also create instances of custom classes:

```python
@dataclass
class Address:
  street: str

@dataclass
class Person:
    name: str
    address: List[Address]
    social_number: Optional[int] = None
```

You could then feed it a payload like `{"name": "Lucy", address: [{"street": ...}, {...}]}`. 
Flex will create an instance of `Person`, that has a list of 2 Address instances.

Note: The basic types `str, bool, int, float, dict, list, None` **are ignored** (no conversion occurs).
This is because `json.load()` already returns these values in the proper type. This may change in the future.


### Supported objects and annotations

Flex can be used with:
- Classes and dataclasses
- Enums *(new in 2.0.6)* 
- Functions
- Methods
- `Union[str, bool, int, float, list, dict, None]`  (or any combination of these basic **json-compatible types**)
- These typing constructs, where `T` is your custom class:
  - `List[T]`
  - `Dict[str, T]`
  - `Union[T, List[T]]`  (for APIs that may return a thing-or-list-of-things)
  - `Optional[T]`


### Limitations

- Variable positional args (such as `def fn(*args): ...`) are left untouched.
- Basic json-compatible types are left untouched. This is determined by the annotation, not the actual value.
- If `None` is given as a value to deserialize into anything, `None` is given back. Absolutely no validation occurs in this case.

- You can only `Union` basic json-compatible types, or `List[T], T`
- No support for additional `typing` and `collections` objects other than the ones mentioned in this documentation.

These are subject to change.


### About Enums

Enums will resolve by value or name, in this order:

1. By exact value (str/int/etc)
1. By exact name (str)
1. By flexed value (str)
1. By flexed name (str)


## `flex.deserialize`

This is where the magic happens, and is the recommended usage whenever it meets your use case. 

TL;DR: Given that `payload` is a dict,`flex.deserialize(payload, hint=Job)` will convert `payload` into an instance of `Job`.

Here's an example puzzle! An uncanny API returns a messy "transaction" JSON:

```json
{
    "Sold_To": {"Name": "Jon"},
    "Items": [
        {"sku": 123, "price": 19.99},
        {"sku": 234, "price": 13.99},
        {"sku": 0, "price": 0.50, "NOTE": "Forgot the reusable bag at home!!"}
    ],
    "Rebates": {
        "airmiles": {"Flat": 10.0},
        "coupon": [{"Flat": 0.79}, {"Flat":  1.50}],
        "senior": {"Percentage": 2.5}
    },
    "Id": "GgfhAs89876yh.z"
}
```

Wouldn't it be convenient if you could create simple classes/dataclasses around them without any boilerplate?

You can solve it with flex. In one line, too!

Start by designing a hierarchy of classes with annotations that closely follow the API reference.

Remember, casing and underscore are ignored in flex, so you could use pep8 if you want:

```python
# models.py

from dataclasses import dataclass
from typing import List, Dict, Union, Optional


class SkuItem:
    def __init__(self, sku: int, price: float) -> None:
        self.sku = sku
        self.price = price


@dataclass
class Rebate:
    percentage: Optional[float] = None
    flat: Optional[float] = None


@dataclass
class Customer:
    name: str


@dataclass
class Transaction:
    sold_to: Customer
    items: List[SkuItem]
    rebates: Dict[str, Union[Rebate, List[Rebate]]]
```

Did you notice any flex-related boilerplate in the snippet above? No? Good! :)

Here's how you can use the flex deserializer to bend the furious API response into your perfect python classes:

```python
payload = {
    "Sold_To": {"Name": "Jon"},
    "Items": [
        {"sku": 123, "price": 19.99},
        {"sku": 234, "price": 13.99},
        {"sku": 0, "price": 0.50, "NOTE": "Forgot the reusable bag at home!!"}
    ],
    "Rebates": {
        "airmiles": {"Flat": 10.0},
        "coupon": [{"Flat": 0.79}, {"Flat":  1.50}],
        "senior": {"Percentage": 2.5}
    },
    "Id": "GgfhAs89876yh.z"
}

transaction = flex.deserialize(payload, hint=Transaction)
all_transactions = flex.deserialize([payload, payload], hint=List[Transaction])
```

Interesting details:
- Well, the casing worked! :shrug:
- `Id` and `NOTE` were dropped because they were excluded from the `Transaction` model. Time saver; some APIs return _tons_ of data.
- The rebates actually kept the keys, and created `Rebate` instances as the values.
- The value type of the `rebates` dict is either a single `Rebate` instance or a list of them. See the "thing or list of things" section below for considerations.
- In the `all_transactions` variable, `List[Annotation]` was used directly as the hint. Nifty!


## `@flex` and `flex(obj)`

There is a decorator version of `deserialize`.

`from coveo_functools.flex import flex`

It returns a function, method or class wrapped in `flex.deserialize` magic.
When called, the wrapper will automatically adjust the call arguments to match the wrapped object, call the wrapped object with them, and return the response.

`flex` can be used:
- as a decorator over classes, methods and functions
- inline to call a function or to create flexible factories

When used inline, you can adjust a payload for any callable:

```python
from some_3rd_party import calculate_price

price = flex(calculate_price)(**payload)
```

You can also generate "flexible" factories, for instance to be used as a delegate:

```python
from some_3rd_party import ThisClass

factory: Callable[..., T] = flex(ThisClass)
instance1 = factory(**payload1)
instance2 = factory(**payload2)
```


When used as a decorator, all invocations are automatically handled for all callers:

```python
@flex
def calculate_price(sold_to: Customer, items: Union[SkuItems, List[SkuItems]]) -> float:
    ...

# breaks static analysis; wrong argument shown for demonstration purposes
price = calculate_price(SoldTo=dict(Name="Marie"), items={"sku": 123, "price": 19.99})
```

You could adjust the `Transaction` from earlier class like this:

```python
@flex
@dataclass
class Transaction:
    sold_to: Customer
    items: List[SkuItem]
    rebates: Dict[str, Union[Rebate, List[Rebate]]]
```

So that you can drop the explicit calls to `flex.deserialize` and use them directly:

```python
one_transaction = Transaction(**payload)
list_transactions = [Transaction(**t) for t in [payload, payload]]
```


### `flex` or `deserialize`?

Favor `flex.deserialize` over the decorator pattern:
- This will make the usages explicit rather than implicit.
- The additional wrappers created by the decorator may affect performance in the presence of huge structures.
- You can `flex.deserialize([], hint=List[T])` and get a list, but you cannot `flex(List[T])` directly (both methods demonstrated below)

Generally, it leads to a better design because you end up wiring the `flex.deserialize` call next to the `json.load()` call in a generic manner, and that's 100% of the `flex` code you'll ever need:


```python
class ApiWrapper:
    def get_transaction(self, id: int) -> Transaction:
        return self._do_request("GET", f"api/transactions/{id}", hint=Transaction)

    def get_all_transactions(self) -> List[Transaction]:
        return self._do_request("GET", "api/transactions", hint=List[Transaction])
  
    def _do_request(self, method: str, url: str, hint: T) -> T:
        response = self._session.request(method=method, url=url)
        return flex.deserialize(response.json, hint=hint)
```

Because explicit is better than implicit, the above design is generally easier to understand than the one below, where `Transaction` is assumed to be decorated with `@flex`:

```python
class ApiWrapper:
    def get_transaction(self, id: int) -> Transaction:
        return Transaction(**self._do_request("GET", f"api/transactions/{id}"))

    def get_all_transactions(self) -> List[Transaction]:
        return [Transaction(**data) for data in self._do_request("GET", "api/transactions")]
  
    def _do_request(self, method: str, url: str) -> Any:
        response = self._session.request(method=method, url=url)
        return response.json
```


## Consideration for mypy

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

# `unflex`

Unflex is one of the utilities used by `flex.deserializer`.

It is responsible for adjusting the keyword arguments of a dictionary, so that they match the argument names of a target function.


It does not perform any conversion; all it does is matching keys.
Extra keys are dropped by default:

```python
from coveo_functools.flex import unflex

def fn(arg1: str, arg2: str) -> None:
    ...

assert unflex(fn, {"ARG1": ..., "ArG_2": ..., "extra": ...}) == {"arg1": ..., "arg2": ...}
```

Note: To target classes, you need to `unflex(cls.__init__, ...)`


## `@flexcase`

`flexcase` is the decorator version of `unflex`:


```python
from coveo_functools.flex import flexcase

@flexcase
def fn(arg1: str, arg2: str) -> str:
    return f"{arg1} {arg2}"


assert fn(ARG1="hello", _arg2="world", extra=...) == "hello world"
```


# `dispatch`

An enhanced version of [functools.singledispatch](https://docs.python.org/3.8/library/functools.html#functools.singledispatch):


- Adds support for `Type[]` annotations (singledispatch only works on instances)
- You are no longer limited to the first argument of the method
- You can target an argument by its name too, regardless of its position


## `finalizer`

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


## `wait.until()`

Waits for a condition to happen. Can be configured with exceptions to ignore.

```python
from coveo_functools import wait
import requests

def _ready() -> bool:
    return requests.get('/ping').status_code == 200

wait.until(_ready, timeout_s=30, retry_ms=100, handle_exceptions=ConnectionError,
           failure_message="The service failed to respond in time.")
```

## `wait.Backoff`

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
