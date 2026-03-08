# Issue 03: No Schema Validation on PRD JSON Output

## Instructions for AI

You are a professional AI engineer reviewing a pipeline orchestration system. Your role:

1. **Understand** the problem described below fully. Ask clarifying questions if anything is unclear.
2. **Recommend** concrete improvements with trade-offs. Discuss alternatives.
3. **Do NOT implement** anything until the user explicitly says to proceed.
4. **Ask questions** about edge cases, scope, and priorities before proposing solutions.

Read the referenced files to get full context before making recommendations.

---

## System Overview

Ralph Pipeline orchestrates multi-milestone software projects using AI agents. In Phase 1, the PRD Writer (a Claude AI agent) generates a PRD JSON file (`tasks/prd-mN.json`) containing user stories with acceptance criteria. This JSON is consumed by:

- **Ralph** (Phase 2) — reads stories, picks the next one, implements it
- **QA** (Phase 3) — scans story notes for test IDs, checks acceptance criteria
- **Bugfix cycle** — QA marks stories with `passes=false` for Ralph to retry

The PRD JSON is the **contract** between PRD generation, coding, and quality review. Its structure matters critically.

---

## The Problem

Phase 1 invokes Claude to produce `tasks/prd-mN.json`. The **only post-check** is whether the file exists:

```python
# From src/ralph_pipeline/phases/prd_generation.py, lines 90-97:

if not prd_json.exists():
    raise PhaseError(
        f"PRD generation for M{milestone.id} did not produce {prd_json}"
    )
```

The JSON is **never validated** against any schema. No field checks, no type checks, no structural verification.

### Expected PRD structure

The PRD generation prompt specifies:
```
- Follow the exact JSON structure with userStories array, each having:
  id, title, description, acceptanceCriteria, priority, passes (false), notes.
```

### What can go wrong

| Defect | Impact | When it surfaces |
|--------|--------|-----------------|
| Missing `userStories` array | `_check_all_pass()` returns False (no stories found) → Ralph thinks nothing is done | Phase 2 — Ralph loops max iterations doing nothing |
| Wrong field name (`acceptance_criteria` vs `acceptanceCriteria`) | QA can't find criteria | Phase 3 — QA gives uninformed verdict |
| Missing `notes` field | `_extract_milestone_test_ids()` finds no test IDs | Phase 3 — coverage analysis reports 0 expected tests |
| Malformed `priority` values | Story ordering undefined | Phase 2 — Ralph picks stories in random order |
| `passes` field missing or wrong type | All-pass check breaks | Phase 2 — can't detect completion |
| Extra wrapper object (e.g., `{"prd": {"userStories": [...]}}`) | All downstream parsing fails | Phase 2-3 — silent failures |

### Downstream code that assumes the schema

**Story completion check** (`ralph_execution.py`):
```python
def _check_all_pass(prd_path: Path) -> bool:
    data = json.loads(prd_path.read_text())
    stories = data.get("userStories", [])
    if not stories:
        return False
    return all(s.get("passes", False) for s in stories)
```

**Test ID extraction** (`qa_review.py`):
```python
def _extract_milestone_test_ids(prd_path: Path) -> list[str]:
    prd = json.loads(prd_path.read_text())
    for story in prd.get("userStories", []):
        notes = story.get("notes", "")
        for m in pattern.finditer(notes):
            ids.add(m.group(1))
```

Both use `.get()` with defaults, which means a wrong schema doesn't crash — it **silently returns empty data**, and the pipeline continues as if everything is fine.

---

## Affected Files

| File | Role |
|------|------|
| `src/ralph_pipeline/phases/prd_generation.py` | Phase 1 — creates PRD, only checks file existence |
| `src/ralph_pipeline/phases/ralph_execution.py` | `_check_all_pass()` — assumes `userStories[].passes` |
| `src/ralph_pipeline/phases/qa_review.py` | `_extract_milestone_test_ids()` — assumes `userStories[].notes` |
| `src/ralph_pipeline/ai/prompts.py` | `prd_generation_prompt()` — specifies expected structure in english |
| `src/ralph_pipeline/config.py` | No PRD schema model exists |

---

## Impact

- **Severity:** High — the PRD is the central contract between all execution phases
- **Failure mode:** Silent — malformed PRDs don't crash, they produce empty data
- **Frequency:** Every milestone — every PRD is AI-generated with no structural guarantee
- **Blast radius:** A bad PRD cascades through Ralph (wrong stories), QA (no coverage data), and bugfix cycles (can't mark failures)

---

## Questions to Consider

1. Should there be a Pydantic model for the PRD JSON structure (like the existing `PipelineConfig`)?
2. Should validation happen immediately after PRD generation, with retry on failure?
3. Should the validator check not just structure but also basic content quality (e.g., every story has at least one acceptance criterion, notes field is non-empty)?
4. Should the PRD schema be versioned so future changes don't break existing pipelines?
5. How strict should validation be — abort on any deviation, or warn on optional fields and abort only on required ones?
6. Should the PRD generation prompt include a JSON schema example rather than just field names in English?
