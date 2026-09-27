from __future__ import annotations

import os
from pathlib import Path

import anthropic
import pytest

from lotline.ai import client


def test_repo_env_key_is_used_without_mutating_process_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=fake-test-key\n", encoding="utf-8")
    monkeypatch.setattr(client, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    captured: dict[str, object] = {}

    def fake_anthropic(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(anthropic, "Anthropic", fake_anthropic)
    assert client.credentials_available()
    assert "ANTHROPIC_API_KEY" not in os.environ
    client.make_client()
    assert captured["api_key"] == "fake-test-key"
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_offline_mode_refuses_even_when_repo_key_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=fake-test-key\n", encoding="utf-8")
    monkeypatch.setattr(client, "REPO_ROOT", tmp_path)
    monkeypatch.setenv(client.OFFLINE_ENV, "1")
    assert not client.credentials_available()
    with pytest.raises(client.AIUnavailable, match="offline mode"):
        client.make_client()
