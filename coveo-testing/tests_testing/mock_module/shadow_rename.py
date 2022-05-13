from tests_testing.mock_module.inner import inner_function as renamed_else_shadowed


def inner_function() -> None:
    """Before the fix, we would use anything that matched the name without looking if it was the right thing."""
