class ConfigurationError(ValueError):
    """Provider or persisted index configuration is incompatible."""


class ProviderError(RuntimeError):
    """Safe external-provider error with no response body or credentials."""


class InvalidModelResponse(ProviderError):
    """The model did not return the bounded structured answer contract."""
