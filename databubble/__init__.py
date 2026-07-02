# databubble/__init__.py
"""
DataBubble SDK — Statistical Intelligence as a Service.

Quick start:
    from databubble import DataBubble
    db = DataBubble(api_key="dbk_...")
    result = db.skills.univariate(df["price"])
    print(result.summary)
"""

from databubble.client import DataBubble
from databubble.models import SkillResult, MemoryResult, ReconciliationResult, JourneyResult
from databubble.exceptions import (
    DataBubbleError, AuthError, ForbiddenError,
    RateLimitError, SkillError, ServerError, SDKUsageError,
)

__version__ = "0.2.0"
__all__ = [
    "DataBubble",
    "SkillResult",
    "MemoryResult",
    "ReconciliationResult",
    "JourneyResult",
    "DataBubbleError",
    "AuthError",
    "ForbiddenError",
    "RateLimitError",
    "SkillError",
    "ServerError",
    "SDKUsageError",
]
