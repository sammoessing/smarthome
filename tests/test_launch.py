"""Tests for the go-live launcher helpers."""

import os

from app import launch


class TestLLMConfig:
    def test_uses_persisted_key(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CONNECT4_HOME", str(tmp_path))
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        (tmp_path / "groq-key.txt").write_text("gsk_persisted\n")
        launch.ensure_llm_configured()
        assert os.environ["OPENAI_API_KEY"] == "gsk_persisted"

    def test_env_wins_without_prompting(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CONNECT4_HOME", str(tmp_path))
        monkeypatch.setenv("OPENAI_API_KEY", "gsk_from_env")
        monkeypatch.setattr(
            "builtins.input", lambda *_: (_ for _ in ()).throw(AssertionError("should not prompt"))
        )
        launch.ensure_llm_configured()
        assert os.environ["OPENAI_API_KEY"] == "gsk_from_env"

    def test_prompts_and_persists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CONNECT4_HOME", str(tmp_path))
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setattr("builtins.input", lambda *_: "gsk_typed")
        launch.ensure_llm_configured()
        assert os.environ["OPENAI_API_KEY"] == "gsk_typed"
        assert (tmp_path / "groq-key.txt").read_text().strip() == "gsk_typed"

    def test_blank_answer_skips(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CONNECT4_HOME", str(tmp_path))
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setattr("builtins.input", lambda *_: "")
        launch.ensure_llm_configured()
        assert "OPENAI_API_KEY" not in os.environ


class TestAccessCode:
    def test_generated_and_persisted(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CONNECT4_HOME", str(tmp_path))
        # register the var with monkeypatch (empty = unset for the launcher)
        # so the value ensure_access_code writes is undone after the test
        monkeypatch.setenv("ACCESS_CODE", "")
        code = launch.ensure_access_code()
        assert code.startswith("C4-") and len(code) == 9
        # same code on the next run
        monkeypatch.setenv("ACCESS_CODE", "")
        assert launch.ensure_access_code() == code

    def test_env_wins(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CONNECT4_HOME", str(tmp_path))
        monkeypatch.setenv("ACCESS_CODE", "my-own-code")
        assert launch.ensure_access_code() == "my-own-code"


class TestTunnelURLParsing:
    def test_finds_trycloudflare_url(self):
        line = ("2026-07-11T22:00:00Z INF +  Your quick Tunnel: "
                "https://random-words-here-1234.trycloudflare.com +")
        m = launch.TUNNEL_URL_RE.search(line)
        assert m.group(0) == "https://random-words-here-1234.trycloudflare.com"

    def test_ignores_other_urls(self):
        assert launch.TUNNEL_URL_RE.search("see https://example.com/docs") is None


class TestPlatformAssets:
    def test_current_platform_has_an_asset(self):
        # every platform we ship launchers for must map to a binary
        assert launch.CLOUDFLARED_ASSETS.get(launch._platform_key()) is not None
