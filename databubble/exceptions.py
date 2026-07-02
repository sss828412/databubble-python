# databubble/exceptions.py
"""
Typed exceptions for the DataBubble SDK.
Every HTTP error from the API maps to a specific exception class
so callers can handle them explicitly without parsing status codes.
"""


class DataBubbleError(Exception):
    """Base exception for all SDK errors."""
    def __init__(self, message: str, status_code: int = 0, response_body: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body or {}


class AuthError(DataBubbleError):
    """Invalid or missing API key. HTTP 401."""
    pass


class ForbiddenError(DataBubbleError):
    """Skill not available on this tier. HTTP 403."""
    pass


class RateLimitError(DataBubbleError):
    """Monthly call limit reached. HTTP 429."""
    pass


class SkillError(DataBubbleError):
    """Skill executed but returned an error (bad input, halted, etc). HTTP 400."""
    pass


class ServerError(DataBubbleError):
    """Unexpected server error. HTTP 5xx."""
    pass


class SDKUsageError(Exception):
    """
    Raised for incorrect SDK usage — wrong argument types, missing required args.
    Not an API error — never reaches the server.
    """
    pass
