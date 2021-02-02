# coveo-styles

Don't let your CLI app spit out hundreds of boring lines!

Manage your user feedback a bit like you manage logs, and get bonus colors and emojis just because we can!

This module provides an `echo` symbol that you can use instead of `print` for convenience.

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

It's even nicer with colors! :) This doc needs a few animated gifs!



# exception hook

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

Unhandled exceptions (those that are not wrapped by an ExitWithFailure), will display the usual python feedback and stacktrace.



# hunting for emojis

Emoji support is provided by the [emoji](https://pypi.org/project/emoji/) package. 
Their description provides different links to help with your emoji hunt, but for some reason not everything is supported or has the name it should have.

The only foolproof way I have found is to actually inspect the `emoji` package, either by opening `site-packages/emoji/unicode_codes/en.py` in my IDE or programmatically like this:

```python
from coveo_styles.styles import echo
from emoji.unicode_codes.en import EMOJI_UNICODE_ENGLISH, EMOJI_ALIAS_UNICODE_ENGLISH

query = 'smile'.lower()

for emoji_name in {*EMOJI_UNICODE_ENGLISH, *EMOJI_ALIAS_UNICODE_ENGLISH}:
    emoji_name = emoji_name.strip(':')
    if query in emoji_name.lower():
        echo.normal(f'{emoji_name}: !!{emoji_name}!!')
```

```
sweat_smile: 😅
cat_face_with_wry_smile: 😼
smile: 😄
smiley: 😃
smiley_cat: 😺
smile_cat: 😸
```
