# coveo-settings

Whenever you want the user to be able to configure something through an environment variable, this module has your back:

```python
from coveo_settings import StringSetting, BoolSetting

DATABASE_URL = StringSetting('project.database.url')
DATABASE_USE_SSL = BoolSetting('project.database.ssl')
```

The user can then configure the environment variables `project.database.url` and `project.database.ssl` to configure the application.

When accessed, the values are automatically converted to the desired type:

- `StringSetting` will always be a string
- `BoolSetting` is either True or False, but accepts "yes|no|true|false|1|0" as input (case-insensitive, of course)
- `IntSetting` and `FloatSetting` are self-explanatory
- `DictSetting` allows you to use JSON maps
- `PathSetting` gives a Path instance, and also implements PathLike and the `/` operator

If the input cannot be converted to the value type, an `TypeConversionConfigurationError` exception is raised.

A default (fallback) value may be specified. The fallback may be a `callable`.

A validation callback may be specified for custom logic and error messages.

Not limited to environment variables; supports redirection to custom implementations.

**A setting can be set as sensitive for logging purposes. When logging, use repr(setting) to get the correct representation.**



## Accessing the value

There are various ways to obtain the value:

```python
from coveo_settings import BoolSetting

DATABASE_USE_SSL = BoolSetting('project.database.ssl')

# this method will raise an exception if the setting has no value and no fallback
use_ssl = bool(DATABASE_USE_SSL)
assert use_ssl in [True, False]

# this method will not raise an exception
use_ssl = DATABASE_USE_SSL.value
assert use_ssl in [True, False, None]

# use "is_set" to check if there is a value set for this setting; skips validation check
if DATABASE_USE_SSL.is_set:
    use_ssl = bool(DATABASE_USE_SSL)

# use "is_valid" to verify if the value passes the validation callback. implies is_set.
if not DATABASE_USE_SSL.is_valid:
    ...
```


## Loose environment key matching

Matching the key of the environment variable `project.database.ssl` is done very loosely:

- case-insensitive
- dots and underscores are ignored completely (`foo_bar` and `f__ooba.r` are equal)
    - useful for some runners that don't support dots in environment variable keys


## Use ready validation

You can quickly validate that a string is in a specific list like this:

```python
from coveo_settings.settings import StringSetting
from coveo_settings.validation import InSequence

ENV = StringSetting("environment", fallback="dev", validation=InSequence("prod", "staging", "dev"))
```


## Redirection

You can register custom redirection schemes in order to support any data source.

Much like `https://` is a clear scheme, you may register callback functions to trigger when the value of a setting
starts with the scheme(s) you define. For instance, let's support a custom API and a file storage: 

```python
from coveo_settings import settings_adapter, StringSetting, ConfigValue


@settings_adapter("internal-api::")
def internal_api_adapter(key: str) -> ConfigValue:
    # the scheme was automatically removed for convenience; only the resource remains
    assert "internal-api::" not in key
    return "internal api"  # implement logic to obtain value from internal api
    

@settings_adapter("file::", strip_scheme=False)
def file_adapter(key: str) -> ConfigValue:
    # you can keep the scheme by specifying `strip_scheme=False`
    assert key.startswith("file::")
    return "file adapter"  # implement logic to parse the key and retrieve the setting value 


assert StringSetting('...', fallback="internal-api::settings/user-name").value == "internal api"
assert StringSetting('...', fallback="file::settings.yaml/user-name").value == "file adapter"


# even though we used `fallback` above, the redirection is driven by the user:
import os

REDIRECT_ME = StringSetting('test')
os.environ['test'] = "file::user.json::name"
assert REDIRECT_ME.value == "file adapter"
os.environ['test'] = "internal-api::url"
assert REDIRECT_ME.value == "internal api"
```

Keep in mind that there's no restriction on the prefix scheme; it's your responsibility to pick something unique 
that can be set as the value of an environment variable.


### Redirection is recursive

The value of a redirection may be another redirection and may juggle between adapters. 
A limit of 50 redirections is supported:

```python
import os

from coveo_settings import StringSetting


os.environ["expected"] = "final value"
os.environ["redirected"] = "env->expected"
os.environ["my-setting"] = "env->redirected"

assert StringSetting("my-setting").value == "final value"
```

### Builtin environment redirection

The builtin redirection scheme `env->` can be used to redirect to a different environment variable.
The example below demonstrates the deprecation/migration of `my-setting` into `new-setting`: 

```python
import os

from coveo_settings import StringSetting

os.environ["new-setting"] = "correct-value"
os.environ["my-setting"] = "env->new-setting"

assert StringSetting("my-setting").value == "correct-value"
```

## Cached

You can set a setting to cache the first valid value with `cached=True`.
This is particularly useful in redirection scenarios to avoid repeating requests too often.


## Setting the value

You can override the value using `setting.value = "some value"` and clear the override with `setting.value = None`. 
Clearing the override resumes the normal behavior of the environment variables and the fallback value, if set.

This is typically used as a way to propagate CLI switches globally.
For mocking scenarios, refer to the `Mocking` section below.


## Mocking

When you need a setting value for a test, use the `mock_config_value` context manager:

```python
from coveo_settings import StringSetting
from coveo_settings.mock import mock_config_value

SETTING = StringSetting(...)

assert not SETTING.is_set
with mock_config_value(SETTING, 'new-value'):
    assert SETTING.is_set
```

You can also clear the value:

```python
from coveo_settings import StringSetting
from coveo_settings.mock import mock_config_value

SETTING = StringSetting(..., fallback='test')

assert SETTING.is_set
with mock_config_value(SETTING, None):
    assert not SETTING.is_set
```
