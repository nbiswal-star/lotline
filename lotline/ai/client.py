"""One call path to Claude for every AI reader in LotLine.

All AI features share these rules:

* The client is created lazily, only when a feature is invoked, never at import or app start.
* Credentials come from the SDK's normal chain (``ANTHROPIC_API_KEY`` etc.). A git-ignored
  ``.env`` at the repo root is read for ``ANTHROPIC_API_KEY`` if the variable is not already set.
  Key values are never logged, stored or shown.
* Output is constrained with structured outputs (a JSON schema). The caller still validates every
  field; schema-valid is not the same as true.
* Every failure (no key, network, timeout, rate limit, refusal, truncation, bad JSON) raises
  ``AIUnavailable`` or ``AIOutputError`` with a user-safe reason, so features can fall back.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MODEL = "claude-opus-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16000
DEFAULT_TIMEOUT_S = 60.0

REPO_ROOT = Path(__file__).resolve().parents[2]


class AIUnavailable(RuntimeError):
    """Claude could not be reached or declined; the feature must fall back."""


class AIOutputError(ValueError):
    """Claude answered, but the answer is unusable (truncated, empty, not JSON)."""


def _load_dotenv_key() -> None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    env = REPO_ROOT / ".env"
    try:
        lines = env.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        name, sep, value = line.strip().partition("=")
        if sep and name.strip() == "ANTHROPIC_API_KEY" and value.strip():
            os.environ["ANTHROPIC_API_KEY"] = value.strip().strip('"').strip("'")
            return


OFFLINE_ENV = "LOTLINE_OFFLINE"


def offline_mode() -> bool:
    """``LOTLINE_OFFLINE=1`` forces every AI reader offline (cached, re-verified results only)."""
    return os.environ.get(OFFLINE_ENV, "").strip().lower() in {"1", "true", "yes"}


def credentials_available() -> bool:
    """True when an API key (or auth token) is configured and offline mode is off; no network call."""
    if offline_mode():
        return False
    _load_dotenv_key()
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def make_client(timeout_s: float = DEFAULT_TIMEOUT_S) -> Any:
    if offline_mode():
        raise AIUnavailable("offline mode (LOTLINE_OFFLINE=1)")
    if not credentials_available():
        raise AIUnavailable("no API key configured")
    try:
        import anthropic
    except Exception as exc:  # noqa: BLE001
        raise AIUnavailable("anthropic SDK not installed") from exc
    return anthropic.Anthropic(timeout=timeout_s, max_retries=1)


@dataclass(frozen=True)
class AIResponse:
    data: dict[str, Any]
    model: str
    request_id: str | None


def call_structured(system: str, user: str, schema: dict[str, Any], *, client: Any = None,
                    effort: str = "medium", timeout_s: float = DEFAULT_TIMEOUT_S,
                    max_tokens: int = MAX_TOKENS) -> AIResponse:
    """One Claude request whose output must match ``schema``; returns the parsed object."""
    if client is None:
        client = make_client(timeout_s)
    try:
        import anthropic
        errors: tuple[type[BaseException], ...] = (anthropic.APIError,)
    except Exception:  # noqa: BLE001 - fake clients in tests
        anthropic = None  # type: ignore[assignment]
        errors = ()
    try:
        # Structured outputs and effort are available on the stable Messages API.
        # Test doubles from the early build expose only beta.messages; keep that
        # narrow compatibility path without requiring the fallback beta in live use.
        messages = client.messages if hasattr(client, "messages") else client.beta.messages
        response = messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": user}],
        )
    except errors as exc:  # type: ignore[misc]
        raise AIUnavailable(_safe_reason(exc, anthropic)) from exc
    stop = getattr(response, "stop_reason", None)
    if stop == "refusal":
        raise AIUnavailable("Claude declined this request")
    if stop == "max_tokens":
        raise AIOutputError("response truncated")
    text = "".join(getattr(b, "text", "") for b in getattr(response, "content", [])
                   if getattr(b, "type", None) == "text").strip()
    if not text:
        raise AIOutputError("empty response")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIOutputError("response was not valid JSON") from exc
    if not isinstance(data, dict):
        raise AIOutputError("response was not a JSON object")
    return AIResponse(data=data, model=getattr(response, "model", MODEL),
                      request_id=getattr(response, "_request_id", None))


def _safe_reason(exc: BaseException, anthropic: Any) -> str:
    if anthropic is None:
        return "Claude request failed"
    if isinstance(exc, anthropic.AuthenticationError):
        return "credentials were rejected"
    if isinstance(exc, anthropic.RateLimitError):
        return "rate limited; try again shortly"
    if isinstance(exc, anthropic.APITimeoutError):
        return "request timed out"
    if isinstance(exc, anthropic.APIConnectionError):
        return "no network connection to Claude"
    if isinstance(exc, anthropic.APIStatusError):
        return f"Claude service error ({exc.status_code})"
    return "Claude request failed"
