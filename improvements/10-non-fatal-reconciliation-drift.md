# Issue 10: Reconciliation Is Non-Fatal — Spec Drift Compounds Silently

## Instructions for AI

You are a professional AI engineer reviewing a pipeline orchestration system. Your role:

1. **Understand** the problem described below fully. Ask clarifying questions if anything is unclear.
2. **Recommend** concrete improvements with trade-offs. Discuss alternatives.
3. **Do NOT implement** anything until the user explicitly says to proceed.
4. **Ask questions** about edge cases, scope, and priorities before proposing solutions.

Read the referenced files to get full context before making recommendations.

---

## System Overview

Ralph Pipeline runs Phase 5 (Spec Reconciliation) after each milestone is merged and verified. The reconciliation step:

1. Reads `progress.txt` and QA reports for the completed milestone
2. Compares what was actually built vs. what the specs say
3. Updates upstream docs (requirements, architecture, design) to match reality
4. Records changes in `docs/05-reconciliation/mN-changes.md`

This keeps specs as the "source of truth" for future milestones.

---

## The Problem

Phase 5 is explicitly **non-fatal**. If reconciliation fails twice, the pipeline logs a warning and continues:

### From `src/ralph_pipeline/phases/reconciliation.py`:

```python
def run_reconciliation(milestone, config, claude, git, plogger, project_root):
    """Run spec reconciliation — 2 attempts, non-fatal."""

    # ... setup ...

    for attempt in range(1, 3):
        try:
            claude.run(prompt, model=config.models.reconciliation, ...)
        except ClaudeError:
            plogger.warning(f"Spec Reconciler attempt {attempt} failed for M{milestone.id}")

        if changelog.exists():
            git.commit_all(f"docs: spec reconciliation after M{milestone.id}")
            plogger.success(f"Reconciliation complete for M{milestone.id}")
            return

        if attempt == 1:
            plogger.info("Changelog not produced — retrying reconciliation (attempt 2)")

    plogger.warning(
        f"Spec Reconciler did not produce {changelog} after 2 attempts — continuing.\n"
        f"Future milestone PRDs may reference stale specs. Consider running /spec_reconciler manually."
    )
```

The warning explicitly acknowledges the risk: "Future milestone PRDs may reference stale specs."

### How drift compounds

Consider a 5-milestone project where reconciliation fails for milestones 2 and 4:

```
M1 → Reconciled ✓ (specs updated to match reality)
M2 → Reconciliation FAILED ✗ (specs NOT updated)
M3 → PRD Writer reads stale specs from M2's deviations
     → context.md has contradictions: "Architecture says X" but codebase shows Y
     → Ralph implements based on... which one?
     → Reconciled ✓ (but reconciling against already-stale specs)
M4 → Reconciliation FAILED ✗ (now TWO layers of drift)
M5 → PRD Writer reads specs with M2 AND M4 deviations unreconciled
     → Architecture docs describe a system 3 milestones behind reality
```

### The contradiction in context.md

The PRD Writer's context bundle includes:
- **Architecture sections** (from docs) — may be stale
- **Codebase snapshot** (from actual files) — always current

When these contradict each other, Ralph must choose. The instructions say to read context.md as authoritative, but context.md itself contains conflicting sections.

### Even "successful" reconciliation has limits

From `spec_reconciler/SKILL.md`, the reconciler categorizes changes:

- **SMALL TECHNICAL** — auto-applied (typos, paths, minor types)
- **FEATURE DESIGN** — needs user approval
- **LARGE TECHNICAL** — needs user approval

In automated pipeline mode, the reconciliation prompt says: "Auto-apply ALL changes (pipeline trusts QA — no manual approval needed)." But the skill instructions define approval gates for feature/large changes. This creates a potential conflict in the reconciler's behavior.

### From the reconciliation prompt

```python
def reconciliation_prompt(...) -> str:
    return f"""{skill_content}

Instructions:
- Auto-apply ALL changes (pipeline trusts QA — no manual approval needed)
- Update spec docs to match reality where implementation deviated
- Record all changes in {recon_dir}/m{milestone}-changes.md"""
```

The prompt overrides the skill's autonomy levels. Whether the reconciler AI correctly handles this override is AI-dependent.

---

## Affected Files

| File | Role |
|------|------|
| `src/ralph_pipeline/phases/reconciliation.py` | Phase 5 — non-fatal, 2 attempts |
| `src/ralph_pipeline/ai/prompts.py` | `reconciliation_prompt()` — overrides skill autonomy levels |
| `src/ralph_pipeline/data/skills/spec_reconciler/SKILL.md` | Defines 3 autonomy levels; pipeline overrides to auto-apply all |
| `src/ralph_pipeline/data/skills/prd_writer/SKILL.md` | Reads upstream docs that may be stale |
| `src/ralph_pipeline/runner.py` | `_run_reconciliation()` — calls Phase 5, doesn't check outcome |
| `src/ralph_pipeline/state.py` | No tracking of reconciliation success/failure per milestone |

### Runner code — reconciliation outcome ignored

```python
def _run_reconciliation(self) -> None:
    """Phase 5: Spec reconciliation."""
    run_reconciliation(
        milestone=self.milestone,
        config=self.config,
        claude=self.claude,
        git=self.git,
        plogger=self.plogger,
        project_root=self.project_root,
    )
    self.reconciled()  # Always transitions to complete, regardless of outcome
```

---

## Impact

- **Severity:** Medium-High over multi-milestone projects — each failed reconciliation compounds
- **Failure mode:** Silent degradation — PRD quality declines as specs drift further from reality
- **Frequency:** Reconciliation failures may be common (AI must read code, compare to specs, update multiple docs)
- **Blast radius:** All future milestones read stale specs; context.md contains internal contradictions

---

## Questions to Consider

1. Should reconciliation failure be tracked in `state.json` so future phases know which milestones have unreconciled drift?
2. Should the PRD Writer receive a warning when prior milestones failed reconciliation, prompting it to trust the codebase over the specs?
3. Should there be more than 2 reconciliation attempts? Or a different retry strategy?
4. Should the pipeline pause and alert the user when reconciliation fails, rather than silently continuing?
5. Should reconciliation become semi-fatal — e.g., non-fatal for the current milestone, but block the next milestone until specs are updated?
6. Should the prompt override of autonomy levels be reconsidered? Should FEATURE DESIGN changes still require user approval even in automated mode?
7. Should there be a "reconciliation debt" metric that the pipeline tracks and reports?
8. Could the pipeline do a simpler, deterministic reconciliation for the most critical items (file paths, API endpoints, data model fields) without relying on AI?
