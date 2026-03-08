# Solution: Structured Milestone Scope Files (Issue 01)

## Problem Solved

Milestone scope files (`docs/05-milestones/milestone-N.md`) were free-form markdown — the only bridge between the Strategy Planner (planning) and the PRD Writer (execution). The PRD Writer AI had to independently re-derive feature→table→endpoint→test-ID mappings from prose, causing silent data loss that surfaced as QA failures 2–3 phases later.

## What Changed

The format was replaced entirely: **`milestone-N.md` → `milestone-N.json`** with a Pydantic-validated schema. The pipeline now parses the JSON, validates it, and injects structured references directly into the PRD Writer prompt — eliminating the AI's need to re-derive mappings from prose.

Legacy `.md` files are still accepted with a deprecation warning.

---

## Files Changed — Pipeline Code

### NEW: `src/ralph_pipeline/milestone_schema.py`

New module defining the structured milestone scope schema. Key exports:

| Export | Purpose |
|--------|---------|
| `MilestoneScope` | Pydantic model — the full JSON schema for `milestone-N.json` |
| `validate_milestone_scope(path)` | Loads + validates a scope file. Raises `MilestoneScopeValidationError` on failure |
| `format_scope_for_prompt(scope)` | Renders parsed scope as structured text for prompt injection |
| `MilestoneScopeValidationError` | Exception with `milestone_id` and `errors` list |

**Schema required fields:** `id`, `slug`, `name`, `execution_order`, `estimated_stories`, `features` (≥1), `story_outline` (≥1 item)

**Schema optional fields:** `dependencies`, `mvp`, `narrative`, `data_model_refs`, `api_refs`, `component_refs`, `ai_agent_refs`, `shared_components`, `test_ids`, `acceptance_criteria`, `notes`, `context_weight`

### MODIFIED: `src/ralph_pipeline/phases/prd_generation.py`

**What changed:**
1. Imports `validate_milestone_scope`, `format_scope_for_prompt`, `MilestoneScopeValidationError` from `milestone_schema`
2. Primary lookup is now `milestone-{id}.json` (was `milestone-{id}.md`)
3. If JSON exists: validates schema → formats for prompt → passes `structured_scope` to prompt builder
4. If JSON missing: falls back to legacy `.md` with deprecation warning
5. If neither exists: raises `PhaseError` (was only checking `.md`)
6. Validation failure raises `PhaseError` immediately (fail-fast, before Claude invocation)

**Key code path (lines 74–100):**
```python
scope_path = milestones_dir / f"milestone-{milestone.id}.json"
if scope_path.exists():
    scope = validate_milestone_scope(scope_path)        # Pydantic validation
    structured_scope = format_scope_for_prompt(scope)   # Render for prompt
else:
    legacy_path = milestones_dir / f"milestone-{milestone.id}.md"
    if legacy_path.exists():
        milestone_doc = str(legacy_path)                # Fallback with warning
    else:
        raise PhaseError(...)                           # Fail fast
```

### MODIFIED: `src/ralph_pipeline/ai/prompts.py`

**`prd_generation_prompt()` signature changed:**
```python
# BEFORE
def prd_generation_prompt(skill_content, milestone_id, slug, milestone_doc,
                          archive_dir, tasks_dir, scripts_dir) -> str:

# AFTER  
def prd_generation_prompt(skill_content, milestone_id, slug, milestone_doc,
                          archive_dir, tasks_dir, scripts_dir,
                          structured_scope: str = "") -> str:
```

When `structured_scope` is non-empty, the prompt includes a new section:
```
## Structured Milestone Scope (machine-parsed from milestone-N.json)

The following structured references have been pre-parsed from the milestone scope file.
Use these as your primary source for features, data model refs, API refs, component refs,
test IDs, and story outline. Do NOT re-derive these from upstream docs — they are authoritative.

[rendered scope tables and lists]
```

The prompt still tells the AI to read `milestone_doc` and upstream docs — but the structured section is marked as **authoritative**, preventing re-derivation drift.

---

## Files Changed — Skills (AI Prompts)

### MODIFIED: `src/ralph_pipeline/data/skills/strategy_planner/SKILL.md`

Phase 4 now produces `milestone-N.json` instead of `milestone-N.md`. The skill includes:
- Full JSON schema example with all fields
- Required vs optional field documentation
- Source reference format (`docs/path.md#section-name`)
- Updated context weight validation referencing JSON fields
- Handover `files_produced` references `.json`

### MODIFIED: `src/ralph_pipeline/data/skills/prd_writer/SKILL.md`

- Description updated to reference "structured milestone scope JSON files"
- Section 1 (Purpose): references JSON instead of markdown
- Section 3 (Startup Protocol): step 2 now says "pipeline injects structured scope data into your prompt" — the AI uses the `Structured Milestone Scope` section as primary source
- Input description: `milestone-N.json` (injected as structured data)

### MODIFIED: `src/ralph_pipeline/data/skills/pipeline_configurator/SKILL.md`

All `milestone-*.md` glob references → `milestone-*.json`:
- Section 3 step 5 (read all milestone scope files)
- Section 4.1 services population (scan all milestones)
- Section 7 rule 3 (scan all milestone scopes)

### MODIFIED: `src/ralph_pipeline/data/skills/spec_reconciler/SKILL.md`

Reference table: `milestone-N.md` → `milestone-N.json`

---

## Impact on Pipeline Executor

### Things that already work (no further changes needed)

1. **`prd_generation.py`** handles both JSON and legacy MD — backward compatible
2. **`prompts.py`** has a default `structured_scope=""` — old callers still work
3. **All downstream phases** (ralph_execution, qa_review, merge_verify, reconciliation) are unaffected — they consume `prd-mN.json` which is unchanged in format

### Things the pipeline executor should be aware of

1. **File lookup order changed**: the pipeline now looks for `milestone-{id}.json` first, then falls back to `milestone-{id}.md`. Any code that constructs milestone scope paths should use `.json` extension.

2. **New validation gate**: `MilestoneScopeValidationError` can now be raised before Claude is ever invoked. The executor should expect `PhaseError` from PRD generation if the scope JSON is malformed.

3. **New module dependency**: `prd_generation.py` imports from `milestone_schema.py`. This module must be included in the package.

4. **Prompt size increase**: when structured scope is injected, the PRD Writer prompt is larger (includes rendered tables). This is intentional — it replaces work the AI was doing by re-reading all docs.

5. **Context weight thresholds** are checked during validation but are **non-fatal warnings** — they don't block execution. The pipeline may want to surface these warnings in its status reporting.

### Milestone scope JSON example (minimal valid)

```json
{
  "id": 1,
  "slug": "foundation",
  "name": "Foundation",
  "execution_order": 1,
  "estimated_stories": 5,
  "features": ["F-1.1"],
  "story_outline": [
    {"order": 1, "summary": "Create users table", "type": "schema"}
  ]
}
```

### Milestone scope JSON example (full)

```json
{
  "id": 2,
  "slug": "user-management",
  "name": "User Management",
  "execution_order": 2,
  "estimated_stories": 7,
  "dependencies": [1],
  "mvp": true,
  "narrative": "Implements full user CRUD with role-based access.",
  "features": ["F-2.1", "F-2.2"],
  "data_model_refs": [
    {"table": "users", "operation": "CREATE", "key_columns": ["id", "email"], "source": "docs/02-architecture/data-model.md#users"}
  ],
  "api_refs": [
    {"endpoint": "/api/users", "method": "POST", "purpose": "Create user", "auth": "public", "source": "docs/02-architecture/api-design.md#create-user"}
  ],
  "component_refs": [
    {"name": "UserForm", "type": "component", "source": "docs/03-design/component-specs.md#UserForm"}
  ],
  "ai_agent_refs": [],
  "shared_components": [
    {"component": "DataTable", "status": "new", "introduced_in": "M1"}
  ],
  "story_outline": [
    {"order": 1, "summary": "Users table migration", "type": "schema"},
    {"order": 2, "summary": "POST /api/users endpoint", "type": "api"},
    {"order": 3, "summary": "UserForm component", "type": "component"}
  ],
  "test_ids": ["T-2.1.01", "API-2.01"],
  "acceptance_criteria": ["All CRUD operations work", "Typecheck passes"],
  "notes": ["Users table has FK to organizations"],
  "context_weight": {"unique_file_paths": 18, "doc_sections": 4, "estimated_stories": 7}
}
```

---

## Test Coverage

- `tests/test_milestone_schema.py` — 18 tests covering schema validation, error cases, prompt formatting
- `tests/test_prompts.py` — updated existing test + new `test_prd_generation_prompt_with_structured_scope`
- All 157 tests pass (1 pre-existing failure in `test_runner.py::test_full_execution_success` is unrelated)
