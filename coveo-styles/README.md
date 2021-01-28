# coveo-styles

Don't let your CLI app spit out hundreds of boring lines!

Manage your user feedback a bit like you manage logs, and get bonus colors and emojis just because we can!

This module provides a `echo` symbol that you can use instead of `print` for convenience.
It is also completely customizable!


## predefined themes for common actions

Here's how a ci run could look like:

```python
from coveo_styles.styles import echo

echo.step("Launching ci operations")
echo.normal("pytest", emoji='hourglass')
echo.normal("black", emoji='hourglass')
echo.noise("Generated test reports in .ci/")
echo.success()
echo.warning("Formatting errors detected")
echo.suggest("The --fix switch will automatically fix these for you and re-run the test !!smile!!")
echo.error("The CI run detected errors you need to fix", pad_after=False)
echo.error_details("Black reported files to reformat", item=True)
echo.error_details("Details as items is nice!", item=True)
```


```
Launching ci operations

⌛ pytest
⌛ black
Generated test reports in .ci/

✔ Success!


⚠ Formatting errors detected


🤖 The --fix switch will automatically fix these for you and re-run the test 😄


💥 The CI run detected errors you need to fix
 · Black reported files to reformat
 · Details as items is nice
```

It's even nicer with the colors! :) This doc needs a few animated gifs!


## bonus: exception hook

Exception handlers may re-raise an exception as an `ExitWithFailure` in order to hide the traceback from the user and show a helpful error message.

Here's an example for the sake of demonstration:

```python
from pathlib import Path
from coveo_styles.styles import ExitWithFailure

try:
    project = Path('./project').read_text()
except FileNotFoundError as exception:
    raise ExitWithFailure(suggestions='Use the --list switch to see which projects I can see') from exception
```

The stacktrace will be hidden, the app will exit with code 1 after printing the exception type and message:

```
! FileNotFoundError: [Errno 2] No such file or directory: 'project'

🤖 Use the --list switch to see which projects I can see
```

Unhandled exceptions (ones that are not wrapped by an ExitWithFailure), will display the usual python feedback and stacktrace.
