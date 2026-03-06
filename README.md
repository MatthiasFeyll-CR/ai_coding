# ralph-pipeline

AI Coding Pipeline Orchestrator — a Python CLI that replaces the 1962-line `pipeline.sh` bash script.

## Install

```bash
pip install -e .
# or from git:
pip install git+https://github.com/<user>/ralph-pipeline.git
```

## Usage

```bash
# Install skills to ~/.claude/skills/
ralph-pipeline install-skills

# Run full pipeline
ralph-pipeline run --config pipeline-config.json

# Resume from interruption
ralph-pipeline run --config pipeline-config.json --resume

# Start from specific milestone
ralph-pipeline run --config pipeline-config.json --milestone 2

# Dry run
ralph-pipeline run --config pipeline-config.json --dry-run

# Validate test infrastructure
ralph-pipeline validate-infra --config pipeline-config.json
```

## Dependencies

- Python 3.11+
- `transitions>=0.9` — FSM library
- `pydantic>=2.0` — Config validation
- `rich>=13.0` — Terminal UI
