import importlib
import pkg_resources
from types import ModuleType
from typing import Dict, Any
import sys


def launch_module_entrypoint(module_name: str, entrypoint: str = None, *args: Any) -> None:
    """
    Launch a module's entrypoint through code.

    Best used for:
        - Creating unit tests for your CLI using the input a user would provide.
    """
    if entrypoint is None:
        assert not args
        entrypoint = sys.argv[1]
        args = tuple(sys.argv[2:])

    if not entrypoint:
        raise Exception('No entrypoint was provided.')

    # obtain the entry point metadata for the desired command
    console_scripts: Dict[str, pkg_resources.EntryPoint] = \
        pkg_resources.get_entry_map(module_name)['console_scripts']
    if entrypoint not in console_scripts:
        raise Exception(f"{entrypoint}: unknown command name.")
    entry_point = console_scripts[entrypoint]

    # import the submodule where the entry point is located
    submodule = importlib.import_module(entry_point.module_name)
    target_function = getattr(submodule, entry_point.attrs[0])

    # launch it with the remaining arguments.
    target_function(args)


def launch_module_entrypoint_from_sys_argv(module: ModuleType) -> None:
    """
    Launch a module's entrypoint based on the command line arguments.

    Best used for:
        - Allowing you to enter your scripts in debug mode from your IDE
        - Launch a script entrypoint from a virtualenv's python executable directly

    ---
    How to implement:
      - in your module, create a `__main__.py` next to the root-most `__init__.py`
      - call this function from `__main__.py`, with your imported module as the argument:

            # if we are not the target, __name__ will be equal to "mymodule.__main__" and not "__main__"
            if __name__ == '__main__':
                import mymodule
                launch_module_entrypoint_from_sys_argv(mymodule)
    ---
    How to use:
      - Let's say mymodule has an entrypoint called "example"
      - In the shell, you would typically call `poetry run example some-options --or-like this`
      - You can instead call it as such:

          python -m mymodule example some-options --or-like this
    """
    if not sys.argv:
        raise Exception("No entrypoint specified.")
    launch_module_entrypoint(module.__name__, sys.argv[1], *sys.argv[2:])
