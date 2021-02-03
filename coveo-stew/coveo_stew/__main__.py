"""python -m entry point"""

if __name__ == "__main__":
    from coveo_systools.script_runner import launch_module_entrypoint_from_sys_argv
    import coveo_stew

    # noinspection PyTypeChecker
    launch_module_entrypoint_from_sys_argv(coveo_stew)
