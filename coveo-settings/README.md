# coveo-settings

Whenever you want the user to be able to configure something through an environment variable, this module has your back:

```python
from coveo_settings.settings import StringSetting, BoolSetting

DATABASE_URL = StringSetting('project.database.url')
DATABASE_USE_SSL = BoolSetting('project.database.ssl')
```

The user can then configure the environment variables `project.database.url` and `project.database.ssl` to configure the application.

When accessed, the values are automatically converted to the desired type:

- `StringSetting` will always be a string
- `BoolSetting` is either True or False, but accepts "yes|no|true|false|1|0" as input (case-insensitive, of course)
- `IntSetting` and `FloatSetting` are self-explanatory
- `DictSetting` allows you to use JSON maps

If the input cannot be converted to the value type, an `InvalidConfiguration` exception is raised.

A default (fallback) value may be specified. The fallback may be a `callable`.


## Accessing the value

There are various ways to obtain the value:

```python
from coveo_settings.settings import StringSetting, BoolSetting

DATABASE_USE_SSL = BoolSetting('project.database.ssl')

# this method will raise an exception if the setting has no value and no fallback
use_ssl = bool(DATABASE_USE_SSL)
assert use_ssl in [True, False]

# this method will not raise an exception
use_ssl = DATABASE_USE_SSL.value
assert use_ssl in [True, False, None]

# use "is_set" as a shorthand for "value is not None": 
if DATABASE_USE_SSL.is_set:
    use_ssl = bool(DATABASE_USE_SSL)
```


## Loose environment key matching

Matching the key of the environment variable `project.database.ssl` is done very loosely:

- case-insensitive
- dots and underscores are ignored completely (`foo_bar` and `f__ooba.r` are equal)
    - useful for some runners that don't support dots in environment variable keys
    

## Mocking

When you need a setting value for a test, use the `mock_config_value` context manager:

```python
from coveo_settings.settings import mock_config_value, StringSetting

SETTING = StringSetting(...)

assert not SETTING.is_set
with mock_config_value(SETTING, 'new-value'):
    assert SETTING.is_set
```

You can also clear the value:

```python
from coveo_settings.settings import mock_config_value, StringSetting

SETTING = StringSetting(..., fallback='test')

assert SETTING.is_set
with mock_config_value(SETTING, None):
    assert not SETTING.is_set
```
