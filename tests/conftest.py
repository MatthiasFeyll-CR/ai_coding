"""Pytest configuration — prevent test collection from source modules."""

import ralph_pipeline.ai.prompts as _prompts

# Mark source functions that look like tests to pytest
_prompts.test_fix_prompt.__test__ = False  # type: ignore[attr-defined]
