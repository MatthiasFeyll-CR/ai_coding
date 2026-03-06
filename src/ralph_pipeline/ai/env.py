"""AI environment loader — reads .ai.env from target project, validates credentials."""

from __future__ import annotations

import os
import re
from pathlib import Path

from ralph_pipeline.log import PipelineLogger

# Keys that MUST be present for Claude Code to authenticate via Azure AI Foundry.
REQUIRED_KEYS = {
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_API_KEY",
}

# Additional keys that are derived/exported during credential setup.
DERIVED_ENV = {
    "ANTHROPIC_FOUNDRY_BASE_URL": "ANTHROPIC_BASE_URL",
    "ANTHROPIC_FOUNDRY_API_KEY": "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_USE_FOUNDRY": "1",
}

# Optional keys that can be specified in .ai.env.
OPTIONAL_KEYS = {
    "CLAUDE_MODEL",
    "ANTHROPIC_FOUNDRY_BASE_URL",
    "ANTHROPIC_FOUNDRY_API_KEY",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "CLAUDE_CODE_USE_FOUNDRY",
}

DEFAULT_AI_ENV_FILE = ".ai.env"


class AIEnvError(Exception):
    """Raised when .ai.env is missing or incomplete."""


def load_ai_env(
    project_root: Path, env_file: str = DEFAULT_AI_ENV_FILE
) -> dict[str, str]:
    """Parse a dotenv-style .ai.env file and return key-value pairs.

    Supports:
      - KEY=VALUE
      - KEY="VALUE" (quoted)
      - KEY='VALUE' (single-quoted)
      - Comments (#) and blank lines
    """
    path = project_root / env_file
    if not path.exists():
        raise AIEnvError(
            f"AI credentials file not found: {path}\n"
            f"Create {env_file} with at least: {', '.join(sorted(REQUIRED_KEYS))}"
        )

    env: dict[str, str] = {}
    line_pattern = re.compile(r"^(?:export\s+)?([A-Z_][A-Z0-9_]*)=(.*)$")

    for lineno, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        m = line_pattern.match(line)
        if not m:
            continue

        key = m.group(1)
        value = m.group(2).strip()

        # Strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]

        # Strip inline comments (only outside quotes)
        if "#" in value:
            value = value.split("#")[0].strip()

        env[key] = value

    return env


def validate_ai_env(env: dict[str, str]) -> list[str]:
    """Validate that all required keys are present and non-empty.

    Returns list of error messages (empty = valid).
    """
    errors: list[str] = []
    for key in sorted(REQUIRED_KEYS):
        val = env.get(key, "").strip()
        if not val:
            errors.append(f"Missing or empty: {key}")
        elif val.startswith("your-") or val == "changeme":
            errors.append(f"Placeholder value for {key} — set a real credential")
    return errors


def build_claude_env(
    ai_env: dict[str, str],
    model_override: str = "",
) -> dict[str, str]:
    """Build the full environment dict for Claude Code subprocess calls.

    Merges the current process env with AI credentials and derived keys,
    so Claude Code picks up the correct endpoint and API key.
    """
    # Start from current process env
    result = dict(os.environ)

    # Apply loaded .ai.env values
    result.update(ai_env)

    # Derive Foundry-specific keys from base keys if not already set
    for derived_key, source in DERIVED_ENV.items():
        if derived_key not in ai_env:
            if source in ai_env:
                result[derived_key] = ai_env[source]
            else:
                # It's a literal value (like "1" for CLAUDE_CODE_USE_FOUNDRY)
                result[derived_key] = source

    # Model override from pipeline config takes precedence
    if model_override:
        result["CLAUDE_MODEL"] = model_override
        result["ANTHROPIC_DEFAULT_OPUS_MODEL"] = model_override

    return result


def load_and_validate_ai_env(
    project_root: Path,
    plogger: PipelineLogger,
    env_file: str = DEFAULT_AI_ENV_FILE,
) -> dict[str, str]:
    """Load .ai.env, validate, log results, return the raw env dict.

    Raises AIEnvError on missing file or invalid credentials.
    """
    plogger.info(f"Loading AI credentials from {env_file}...")

    ai_env = load_ai_env(project_root, env_file)

    errors = validate_ai_env(ai_env)
    if errors:
        for err in errors:
            plogger.error(f"  {err}")
        raise AIEnvError(
            f"AI credentials validation failed in {env_file}:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    # Log what we found (masking secrets)
    for key in sorted(REQUIRED_KEYS | OPTIONAL_KEYS):
        val = ai_env.get(key, "")
        if val:
            masked = val[:8] + "..." if len(val) > 12 else val
            if "KEY" in key or "SECRET" in key:
                masked = val[:4] + "****" + val[-4:] if len(val) > 8 else "****"
            plogger.info(f"  {key}={masked}")

    plogger.success(f"AI credentials loaded ({len(ai_env)} keys from {env_file})")
    return ai_env
