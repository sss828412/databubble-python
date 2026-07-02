# databubble/client.py
"""
DataBubble — root client.

Usage:
    from databubble import DataBubble
    db = DataBubble(api_key="dbk_...")
    result = db.skills.univariate(df["price"])
"""

from __future__ import annotations

import json
from typing import Optional

from databubble.exceptions import (
    AuthError, ForbiddenError, RateLimitError,
    SkillError, ServerError, DataBubbleError,
)
from databubble.skills import SkillsClient
from databubble.memory import MemoryClient
from databubble.journeys import JourneysClient


DEFAULT_BASE_URL = "https://api.databubble.ai"


class _HTTPClient:
    """
    Thin HTTP client. Uses httpx if available, falls back to urllib.
    Handles auth header injection and error mapping.
    """

    def __init__(self, api_key: str, base_url: str, timeout: float):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = None
        self._init_session()

    def _init_session(self):
        try:
            import httpx
            self._session = httpx.Client(
                base_url=self._base_url,
                headers={"X-API-Key": self._api_key},
                timeout=self._timeout,
            )
            self._backend = "httpx"
        except ImportError:
            # Fall back to urllib — no session, headers injected per-request
            self._backend = "urllib"

    def _raise_for_status(self, status_code: int, body: dict):
        if status_code == 401:
            raise AuthError(body.get("error", "Invalid API key"), status_code, body)
        if status_code == 403:
            raise ForbiddenError(body.get("error", "Skill not available on this tier"), status_code, body)
        if status_code == 429:
            raise RateLimitError(body.get("error", "Monthly limit reached"), status_code, body)
        if status_code == 400:
            raise SkillError(body.get("error", "Skill returned an error"), status_code, body)
        if status_code >= 500:
            raise ServerError(f"Server error ({status_code})", status_code, body)
        if status_code >= 400:
            raise DataBubbleError(body.get("error", f"HTTP {status_code}"), status_code, body)

    def post_json(self, path: str, payload: dict) -> dict:
        """POST with JSON body. Returns parsed response dict."""
        url = f"{self._base_url}{path}"

        if self._backend == "httpx":
            response = self._session.post(path, json=payload)
            body = response.json()
            self._raise_for_status(response.status_code, body)
            return body
        else:
            import urllib.request, urllib.error
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                url, data=data,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": self._api_key,
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                body = json.loads(e.read())
                self._raise_for_status(e.code, body)

    def post_multipart(self, path: str, fields: dict, files: dict) -> dict:
        """POST with multipart form data. Returns parsed response dict."""
        url = f"{self._base_url}{path}"

        if self._backend == "httpx":
            form_data = {k: v for k, v in fields.items() if v is not None}
            file_data = {}
            for k, v in files.items():
                if isinstance(v, tuple):
                    file_data[k] = v
                else:
                    file_data[k] = v
            response = self._session.post(path, data=form_data, files=file_data)
            body = response.json()
            self._raise_for_status(response.status_code, body)
            return body
        else:
            raise DataBubbleError(
                "Multipart upload requires httpx. "
                "Install with: pip install httpx"
            )

    def close(self):
        if self._backend == "httpx" and self._session:
            self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class DataBubble:
    """
    DataBubble API client.

    Args:
        api_key:  Your API key (starts with dbk_). Get one at databubble.ai.
        base_url: API base URL. Defaults to https://api.databubble.ai.
                  Override for local development: http://localhost:8000
        timeout:  Request timeout in seconds. Default 60.

    Example:
        from databubble import DataBubble
        db = DataBubble(api_key="dbk_...")

        # Single-column skill
        result = db.skills.univariate(df["price"])
        print(result.summary)
        print(result.warnings)

        # Whole-dataset skill
        result = db.skills.missing_values(df)

        # Memory workflow
        mem = db.memory.export(df, label="POS data June 2026")
        mem.save("pos_memory.json")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
    ):
        import os
        resolved_key = api_key or os.environ.get("DATABUBBLE_API_KEY", "")
        if not resolved_key:
            raise ValueError(
                "API key required. Pass api_key= or set DATABUBBLE_API_KEY env var. "
                "Get a key at databubble.ai."
            )
        if not resolved_key.startswith("dbk_"):
            raise ValueError(
                f"Invalid API key format. Keys start with 'dbk_'. Got: {resolved_key[:8]}..."
            )

        self._http = _HTTPClient(resolved_key, base_url, timeout)
        self.skills = SkillsClient(self._http)
        self.memory = MemoryClient(self._http)
        self.journeys = JourneysClient(self._http)

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __repr__(self):
        return f"DataBubble(base_url='{self._http._base_url}')"
