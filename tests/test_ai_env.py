"""Tests for AI environment loading and validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ralph_pipeline.ai.env import (
    AIEnvError,
    build_claude_env,
    load_ai_env,
    load_and_validate_ai_env,
    validate_ai_env,
)


class TestLoadAIEnv:
    def test_loads_basic_env(self, tmp_path: Path):
        (tmp_path / ".ai.env").write_text(
            'ANTHROPIC_BASE_URL="https://example.com/anthropic/"\n'
            "ANTHROPIC_API_KEY=test-key-12345\n"
        )
        env = load_ai_env(tmp_path)
        assert env["ANTHROPIC_BASE_URL"] == "https://example.com/anthropic/"
        assert env["ANTHROPIC_API_KEY"] == "test-key-12345"

    def test_strips_double_quotes(self, tmp_path: Path):
        (tmp_path / ".ai.env").write_text('ANTHROPIC_API_KEY="mykey"\n')
        env = load_ai_env(tmp_path)
        assert env["ANTHROPIC_API_KEY"] == "mykey"

    def test_strips_single_quotes(self, tmp_path: Path):
        (tmp_path / ".ai.env").write_text("ANTHROPIC_API_KEY='mykey'\n")
        env = load_ai_env(tmp_path)
        assert env["ANTHROPIC_API_KEY"] == "mykey"

    def test_ignores_comments_and_blanks(self, tmp_path: Path):
        (tmp_path / ".ai.env").write_text(
            "# This is a comment\n"
            "\n"
            "ANTHROPIC_API_KEY=real-key\n"
            "# Another comment\n"
        )
        env = load_ai_env(tmp_path)
        assert len(env) == 1
        assert env["ANTHROPIC_API_KEY"] == "real-key"

    def test_handles_export_prefix(self, tmp_path: Path):
        (tmp_path / ".ai.env").write_text("export ANTHROPIC_API_KEY=exported-key\n")
        env = load_ai_env(tmp_path)
        assert env["ANTHROPIC_API_KEY"] == "exported-key"

    def test_raises_on_missing_file(self, tmp_path: Path):
        with pytest.raises(AIEnvError, match="not found"):
            load_ai_env(tmp_path)

    def test_custom_filename(self, tmp_path: Path):
        (tmp_path / "custom.env").write_text("ANTHROPIC_API_KEY=custom\n")
        env = load_ai_env(tmp_path, env_file="custom.env")
        assert env["ANTHROPIC_API_KEY"] == "custom"

    def test_multiple_keys(self, tmp_path: Path):
        (tmp_path / ".ai.env").write_text(
            'ANTHROPIC_BASE_URL="https://api.example.com/"\n'
            "ANTHROPIC_API_KEY=key123\n"
            'CLAUDE_MODEL="claude-opus-4-6"\n'
        )
        env = load_ai_env(tmp_path)
        assert len(env) == 3
        assert env["CLAUDE_MODEL"] == "claude-opus-4-6"


class TestValidateAIEnv:
    def test_valid_env(self):
        env = {
            "ANTHROPIC_BASE_URL": "https://example.com/",
            "ANTHROPIC_API_KEY": "real-key-abc123",
        }
        errors = validate_ai_env(env)
        assert errors == []

    def test_missing_key(self):
        env = {"ANTHROPIC_BASE_URL": "https://example.com/"}
        errors = validate_ai_env(env)
        assert len(errors) == 1
        assert "ANTHROPIC_API_KEY" in errors[0]

    def test_empty_value(self):
        env = {
            "ANTHROPIC_BASE_URL": "https://example.com/",
            "ANTHROPIC_API_KEY": "",
        }
        errors = validate_ai_env(env)
        assert len(errors) == 1
        assert "ANTHROPIC_API_KEY" in errors[0]

    def test_placeholder_value(self):
        env = {
            "ANTHROPIC_BASE_URL": "https://example.com/",
            "ANTHROPIC_API_KEY": "your-api-key-here",
        }
        errors = validate_ai_env(env)
        assert len(errors) == 1
        assert "Placeholder" in errors[0]

    def test_all_missing(self):
        errors = validate_ai_env({})
        assert len(errors) == 2


class TestBuildClaudeEnv:
    def test_merges_with_process_env(self):
        ai_env = {
            "ANTHROPIC_BASE_URL": "https://example.com/",
            "ANTHROPIC_API_KEY": "test-key",
        }
        result = build_claude_env(ai_env)
        # Should include process env (PATH, HOME, etc.) plus AI keys
        assert "PATH" in result
        assert result["ANTHROPIC_BASE_URL"] == "https://example.com/"
        assert result["ANTHROPIC_API_KEY"] == "test-key"

    def test_derives_foundry_keys(self):
        ai_env = {
            "ANTHROPIC_BASE_URL": "https://example.com/",
            "ANTHROPIC_API_KEY": "test-key",
        }
        result = build_claude_env(ai_env)
        assert result["ANTHROPIC_FOUNDRY_BASE_URL"] == "https://example.com/"
        assert result["ANTHROPIC_FOUNDRY_API_KEY"] == "test-key"
        assert result["CLAUDE_CODE_USE_FOUNDRY"] == "1"

    def test_explicit_foundry_keys_not_overridden(self):
        ai_env = {
            "ANTHROPIC_BASE_URL": "https://example.com/",
            "ANTHROPIC_API_KEY": "test-key",
            "ANTHROPIC_FOUNDRY_BASE_URL": "https://custom-foundry.com/",
        }
        result = build_claude_env(ai_env)
        assert result["ANTHROPIC_FOUNDRY_BASE_URL"] == "https://custom-foundry.com/"

    def test_model_override(self):
        ai_env = {
            "ANTHROPIC_BASE_URL": "https://example.com/",
            "ANTHROPIC_API_KEY": "test-key",
        }
        result = build_claude_env(ai_env, model_override="claude-sonnet-4-5")
        assert result["CLAUDE_MODEL"] == "claude-sonnet-4-5"
        assert result["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "claude-sonnet-4-5"

    def test_no_model_override_preserves_env(self):
        ai_env = {
            "ANTHROPIC_BASE_URL": "https://example.com/",
            "ANTHROPIC_API_KEY": "test-key",
            "CLAUDE_MODEL": "claude-opus-4-6",
        }
        result = build_claude_env(ai_env, model_override="")
        assert result["CLAUDE_MODEL"] == "claude-opus-4-6"


class TestLoadAndValidateAIEnv:
    def test_success(self, tmp_path: Path):
        (tmp_path / ".ai.env").write_text(
            'ANTHROPIC_BASE_URL="https://example.com/"\n'
            "ANTHROPIC_API_KEY=real-key-abcdef1234\n"
        )
        plogger = MagicMock()
        result = load_and_validate_ai_env(tmp_path, plogger)
        assert result["ANTHROPIC_API_KEY"] == "real-key-abcdef1234"
        plogger.success.assert_called_once()

    def test_missing_file_raises(self, tmp_path: Path):
        plogger = MagicMock()
        with pytest.raises(AIEnvError, match="not found"):
            load_and_validate_ai_env(tmp_path, plogger)

    def test_invalid_credentials_raises(self, tmp_path: Path):
        (tmp_path / ".ai.env").write_text("ANTHROPIC_BASE_URL=https://example.com/\n")
        plogger = MagicMock()
        with pytest.raises(AIEnvError, match="validation failed"):
            load_and_validate_ai_env(tmp_path, plogger)
        plogger.error.assert_called()
