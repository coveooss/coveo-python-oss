class InvalidConfiguration(Exception):
    """Thrown when a setting item is badly configured."""


class TypeConversionConfigurationError(InvalidConfiguration):
    """Thrown when a setting cannot be converted to the appropriate type."""


class MandatoryConfigurationError(InvalidConfiguration):
    """Thrown when a mandatory configuration value isn't set."""


class ValidationConfigurationError(InvalidConfiguration):
    """Thrown when a value fails a custom validation."""


class ValidationCallbackError(InvalidConfiguration):
    """Thrown when a validation type is not supported."""
