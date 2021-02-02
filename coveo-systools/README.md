# coveo-systools

Language and OS related utilities.


Content in a nutshell:

- enhanced subprocess calls
- file and app finding made easy
- safe text write and replace-if-different
- git-repo-root locator
- bool platforms `if WINDOWS or LINUX or MAC or WSL:`


# searching the filesystem

```python
import os
from coveo_systools.filesystem import find_paths, find_application, find_repo_root

os.getcwd()
# '/code/coveo-python-oss/coveo-systools'

find_application('git')
# WindowsPath('C:/Program Files/Git/cmd/git.EXE')  # windows example for completeness

find_repo_root()
# Path('/code/coveo-python-oss')

list(find_paths('pyproject.toml', search_from=find_repo_root(), in_root=True, in_children=True))
# [Path('/code/coveo-python-oss/pyproject.toml'), ...]
```

# enhanced subprocess calls

An opinionated version of `subprocess.check_call` and `subprocess.check_output`.

Adds the following features:
- command line is a variable args (instead of a list)
- automatic conversion of output to a stripped string (instead of raw bytes)
- automatic conversion of Path, bytes and number variables in command line
- automatic filtering of ansi codes from the output
- enhanced DetailedCalledProcessError on error (a subclass of the typical CalledProcessError)

```python
from pathlib import Path
from coveo_systools.subprocess import check_call

check_call('mypy', '--config-file', Path('configs/mypy.ini'), verbose=True)
```


# safe I/O, if changed

Good programming practices requires files to be saved using a temporary filename and then renamed.
This helper takes it a step further by skipping the write operation if the content did not change: 

```python
import json
from pathlib import Path
from coveo_systools.filesystem import safe_text_write

safe_text_write(Path('./path/to/file.txt'), json.dumps(...), only_if_changed=True)
```


# conditional platforms syntactic sugar

Readability is important, not repeating yourself is important.
Forget about `platform.platform()` and use bools directly:

```python
from coveo_systools.platforms import WINDOWS, LINUX, IOS, WSL

if WINDOWS or WSL:
    print("Hello Windows!")
elif LINUX or IOS:
    print("Hello Unix!")
```
