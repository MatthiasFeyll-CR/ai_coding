# Issue 06: Test ID Extraction Is Fragile Regex on Unstructured Text

## Instructions for AI

You are a professional AI engineer reviewing a pipeline orchestration system. Your role:

1. **Understand** the problem described below fully. Ask clarifying questions if anything is unclear.
2. **Recommend** concrete improvements with trade-offs. Discuss alternatives.
3. **Do NOT implement** anything until the user explicitly says to proceed.
4. **Ask questions** about edge cases, scope, and priorities before proposing solutions.

Read the referenced files to get full context before making recommendations.

---

## System Overview

Ralph Pipeline has a test coverage analysis step in Phase 3 (QA Review). It works as follows:

1. **Extract expected test IDs** from the PRD's story notes (regex on AI-generated text)
2. **Search the codebase** for each test ID (grep with heuristic normalization)
3. **Report FOUND/MISSING** — missing IDs are flagged as defects in the QA prompt

This is a **structured pipeline operation** that depends entirely on **unstructured AI-generated text** for both its input (PRD notes) and its search target (Ralph's test naming conventions).

---

## The Problem

### Step 1: Extracting test IDs from PRD notes

In `src/ralph_pipeline/phases/qa_review.py`:

```python
def _extract_milestone_test_ids(prd_path: Path) -> list[str]:
    prd = json.loads(prd_path.read_text())
    ids: set[str] = set()
    pattern = re.compile(
        r"\b(T-[\d.]+|API-[\d.]+|DB-[\d.]+|UI-[\d.]+|"
        r"LOOP-[\d]+|STATE-[\d]+|TIMEOUT-[\d]+|LEAK-[\d]+|"
        r"INTEGRITY-[\d]+|AI-SAFE-[\d]+|SCN-[\d]+|JOURNEY-[\d]+|"
        r"CONC-[\d]+|ERR-[\d]+)\b"
    )
    for story in prd.get("userStories", []):
        notes = story.get("notes", "")
        for m in pattern.finditer(notes):
            ids.add(m.group(1))
    return sorted(ids)
```

This regex assumes test IDs appear as bare tokens in the `notes` string. But `notes` is AI-generated free text. The PRD Writer might format them as:
- `Testing: T-1.1, T-1.2, T-1.3` ← works
- `| T-1.1 | User login | ...` (markdown table) ← works
- `` `T-1.1` `` (backtick-wrapped) ← works (word boundary matches)
- `Testing: [T-1.1](docs/04-test-architecture/test-matrix.md)` ← works
- `T-1.1.01` ← regex captures `T-1.1` (misses `.01` suffix due to greedy `[\d.]+`)
- Notes field is a JSON object instead of string ← crashes
- Test IDs in a nested list or indented block ← works if word boundaries match

The regex is **reasonably robust** for well-formed IDs, but the bigger issue is:

### Step 2: Finding test IDs in the codebase

```python
def _find_implemented_test_ids(test_ids: list[str], search_dir: Path) -> list[str]:
    found: list[str] = []
    for tid in test_ids:
        # Normalize: T-1.2.01 → T_*1_*2_*01
        pattern = tid.replace("-", "_*").replace(".", "_*")
        result = run_command(
            f"grep -rlE '({re.escape(tid)}|{pattern})' {search_dir} "
            f"--include='*.py' --include='*.js' --include='*.ts' "
            f"--include='*.tsx' --include='*.jsx' --include='*.go' "
            f"--include='*.rs' --include='*.rb' 2>/dev/null | head -1",
            ...
        )
```

This assumes Ralph names tests or includes comments matching the exact ID or a normalized version. But Ralph might:
- Name the test `test_user_login` instead of `test_t_1_1_user_login`
- Use a different separator: `test_T1_1` vs `test_T_1_1`
- Put the ID in a docstring vs. the function name
- Not reference the test ID at all (just implement the behavior)

### The compound fragility

The full chain is:
1. Test Architect → writes `T-1.1` in `test-matrix.md` (structured)
2. Strategy Planner → assigns test IDs to milestones (prose)
3. PRD Writer → embeds test IDs in story notes (AI-generated text)
4. Ralph → names tests referencing the ID (AI-generated code)
5. Pipeline → regex-extracts from notes, grep-searches in code (heuristic)

Steps 2, 3, and 4 are all AI-generated with no structural constraint. The pipeline's coverage analysis accuracy depends on all three AIs independently using consistent formatting.

---

## Affected Files

| File | Role |
|------|------|
| `src/ralph_pipeline/phases/qa_review.py` | `_extract_milestone_test_ids()` and `_find_implemented_test_ids()` |
| `src/ralph_pipeline/data/skills/prd_writer/SKILL.md` | Defines how test IDs go into story notes |
| `src/ralph_pipeline/data/skills/qa_engineer/SKILL.md` | QA uses pipeline-provided coverage scan |
| `src/ralph_pipeline/data/skills/test_architect/SKILL.md` | Defines test ID format |

### Key code path

```
_extract_milestone_test_ids(prd_path)     → list of expected test IDs
    ↓
_find_implemented_test_ids(ids, root)     → list of found test IDs
    ↓
_analyze_test_coverage(...)               → "FOUND/MISSING" report string
    ↓
qa_review_prompt(coverage_report=report)  → QA agent sees MISSING as DEFECTS
```

---

## Impact

- **Severity:** Medium-High — false negatives (MISSING when actually implemented) cause unnecessary bugfix cycles; false positives (test not actually needed) waste QA attention
- **Failure mode:** Both silent and noisy — silent when IDs are missed from extraction; noisy when implemented tests aren't found by grep
- **Frequency:** Every milestone QA review
- **Blast radius:** Directly affects QA verdict (PASS/FAIL) and bugfix cycle count

---

## Questions to Consider

1. Should the PRD Writer store test IDs in a **structured field** per story (e.g., `testIds: ["T-1.1", "T-1.2"]`) instead of embedding them in free-text notes?
2. Should Ralph be instructed to register implemented tests in a manifest file (e.g., `.ralph/test-manifest.json`) that the pipeline reads directly?
3. Should the pipeline use AST parsing (e.g., Python's `ast` module for `.py` files) to extract test function names and docstrings, rather than grep?
4. Should the coverage analysis be a hard gate or remain advisory?
5. Is the normalization heuristic (`-` → `_*`, `.` → `_*`) sufficient, or should there be an explicit mapping table?
6. Should the Test Architect's test-matrix.md have a machine-parseable format that the pipeline reads directly, bypassing the PRD notes entirely?
