from tests_testing.mock_module.inner import (
    MockClass,
    inner_function,
    inner_function_wrapper,
    MockClassToRename as RenamedClass,
)


def call_inner_function_from_another_module() -> str:
    return inner_function()


def call_inner_function_wrapper_from_another_module() -> str:
    return inner_function_wrapper()


def return_renamed_mock_class_instance() -> RenamedClass:
    return RenamedClass()


class MockSubClass(MockClass):
    ...
