"""Safe typed provider exceptions. Never leak API keys or response bodies."""

class GatewayError(RuntimeError):
    code = "provider_error"

class ProviderUnavailable(GatewayError):
    code = "provider_unavailable"

class ProviderTimeout(GatewayError):
    code = "provider_timeout"

class ProviderInvalidResponse(GatewayError):
    code = "invalid_provider_response"


class ProviderOutputLimited(ProviderInvalidResponse):
    code = "output_limit_reached"


class ProviderContextLimited(ProviderUnavailable):
    code = "context_limit_reached"
