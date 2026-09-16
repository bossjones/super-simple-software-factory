"""Central credential redaction for persisted runtime and trace data."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from enum import Enum
from typing import Any

REDACTED = "[REDACTED]"

_SAFE_TOKEN_KEYS = {
    "cache_read_tokens",
    "cache_write_tokens",
    "context_tokens",
    "current_tokens",
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "token_count",
    "token_limit",
    "tokens",
    "total_tokens",
}
_SECRET_KEY_WORDS = {
    "access_token",
    "accesstoken",
    "api_key",
    "apikey",
    "auth_token",
    "authtoken",
    "authorization",
    "client_secret",
    "clientsecret",
    "cookie",
    "credential",
    "credentials",
    "github_token",
    "githubtoken",
    "password",
    "passwd",
    "private_key",
    "privatekey",
    "refresh_token",
    "refreshtoken",
    "secret",
    "set_cookie",
    "setcookie",
    "token",
}
_KNOWN_TOKEN_RE = re.compile(
    r"(?i)\b(?:github_pat_[A-Za-z0-9_]{12,}|gh[pousr]_[A-Za-z0-9_]{12,})\b"
)
_BEARER_RE = re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/=-]+")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_ASSIGNMENT_RE = re.compile(
    r"""(?ix)
    (
      \b(?:authorization|api[_-]?key|access[_-]?token|auth[_-]?token|
      refresh[_-]?token|github[_-]?token|client[_-]?secret|password|passwd|secret)\b
      ["']?\s*[:=]\s*
    )
    (?:"[^"]*"|'[^']*'|[^\s,;]+)
    """
)
_BASIC_AUTH_URL_RE = re.compile(r"(https?://[^:/\s]+:)[^@\s]+@", re.IGNORECASE)


def _normalized_key(key: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")


def is_sensitive_key(key: object) -> bool:
    """Return whether a structured field name represents credential material."""
    normalized = _normalized_key(key)
    if normalized in _SAFE_TOKEN_KEYS or normalized.endswith("_tokens"):
        return False
    if normalized in _SECRET_KEY_WORDS or normalized.replace("_", "") in _SECRET_KEY_WORDS:
        return True
    return (
        normalized.endswith("_token")
        or normalized.endswith("_password")
        or normalized.endswith("_secret")
        or normalized.endswith("_api_key")
        or normalized.endswith("_private_key")
    )


def configured_secret_values() -> tuple[str, ...]:
    """Collect configured credential values without ever persisting their names."""
    values = {
        value
        for name, value in os.environ.items()
        if value and len(value) >= 4 and is_sensitive_key(name)
    }
    return tuple(sorted(values, key=len, reverse=True))


def redact_text(text: str, secret_values: tuple[str, ...] | None = None) -> str:
    """Redact configured and recognizable credential values inside free text."""
    redacted = text
    for value in secret_values if secret_values is not None else configured_secret_values():
        redacted = redacted.replace(value, REDACTED)
    redacted = _KNOWN_TOKEN_RE.sub(REDACTED, redacted)
    redacted = _BEARER_RE.sub(r"\1" + REDACTED, redacted)
    redacted = _JWT_RE.sub(REDACTED, redacted)
    redacted = _ASSIGNMENT_RE.sub(r"\1" + REDACTED, redacted)
    return _BASIC_AUTH_URL_RE.sub(r"\1" + REDACTED + "@", redacted)


def sanitize_for_persistence(
    value: Any,
    *,
    secret_values: tuple[str, ...] | None = None,
) -> Any:
    """Recursively retain useful structure while removing credential material."""
    secrets = secret_values if secret_values is not None else configured_secret_values()
    if isinstance(value, str):
        return redact_text(value, secrets)
    if isinstance(value, bytes):
        return redact_text(value.decode(errors="replace"), secrets)
    if isinstance(value, Enum):
        return sanitize_for_persistence(value.value, secret_values=secrets)
    if isinstance(value, Mapping):
        return {
            str(key): (
                REDACTED
                if is_sensitive_key(key)
                else sanitize_for_persistence(item, secret_values=secrets)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [sanitize_for_persistence(item, secret_values=secrets) for item in value]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return sanitize_for_persistence(
            model_dump(mode="json", exclude_none=True),
            secret_values=secrets,
        )
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        return sanitize_for_persistence(attributes, secret_values=secrets)
    return redact_text(str(value), secrets)
