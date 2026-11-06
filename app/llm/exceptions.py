class LLMError(Exception):
    pass


class LLMAuthError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMTransportError(LLMError):
    pass


class LLMAPIError(LLMError):
    pass


class LLMRefusalError(LLMError):
    pass


class LLMUnexpectedResponse(LLMError):
    pass
