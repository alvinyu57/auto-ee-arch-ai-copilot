class ConfigurationError(ValueError):
    """Provider or persisted index configuration is incompatible."""


class ProviderError(RuntimeError):
    """Safe external-provider error with no response body or credentials."""

    def __init__(
        self, message: str, *, code: str | None = None, http_status: int | None = None
    ) -> None:
        super().__init__(message)
        # Never expose arbitrary provider text as an error code.
        self.code = (
            code
            if code
            in {
                "credit_balance_exhausted",
                "insufficient_quota",
                "organization_spend_limit_exceeded",
                "project_spend_limit_exceeded",
                "organization_usage_limit_exceeded",
                "rate_limit_exceeded",
                "slow_down",
                "model_not_found",
                "invalid_api_key",
                "unsupported_parameter",
                "invalid_json_schema",
            }
            else None
        )
        self.http_status = http_status


class InvalidModelResponse(ProviderError):
    """The model did not return the bounded structured answer contract."""


class DocumentIdentityConflict(ValueError):
    """A filename-derived identity requires explicit authorization for replacement."""
