# coveo-itertools

Another spin on iteration goodness.


## dict lookup

A one-liner function to retrieve a value from a dictionary:


```python
from typing import Dict, Any
from coveo_itertools.lookups import dict_lookup


example: Dict[str, Any] = {'nested': {'key': {'lookup': True}}}

assert dict_lookup(example, 'nested', 'key', 'lookup') == True
assert dict_lookup(example, 'not', 'there', default=None) is None
```
