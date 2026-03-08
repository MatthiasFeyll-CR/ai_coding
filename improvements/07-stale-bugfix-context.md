# Issue 07: Bugfix Cycle Operates on Stale Context

## Instructions for AI

You are a professional AI engineer reviewing a pipeline orchestration system. Your role:

1. **Understand** the problem described below fully. Ask clarifying questions if anything is unclear.
2. **Recommend** concrete improvements with trade-offs. Discuss alternatives.
3. **Do NOT implement** anything until the user explicitly says to proceed.
4. **Ask questions** about edge cases, scope, and priorities before proposing solutions.

Read the referenced files to get full context before making recommendations.

---

## System Overview

Ralph Pipeline has a QA bugfix cycle. When QA (Phase 3) issues a FAIL verdict:

1. QA updates the PRD — marks failing stories with `passes=false` and adds notes about what needs fixing
2. Ralph re-runs in "bugfix mode" — shorter iteration count (`stories × 2`)
3. QA re-runs — checks if defects are fixed
4. Repeat up to `max_bugfix_cycles` (default: 3)

During bugfix mode, Ralph reads the same `.ralph/CLAUDE.md` and `.ralph/context.md` from Phase 1.

---

## The Problem

When Ralph enters bugfix mode, the codebase has **already changed substantially** — Ralph implemented several stories during Phase 2. But `.ralph/context.md` was assembled **before Phase 2** and contains a codebase snapshot from that point.

### What's stale in context.md during bugfix

| Section | State during bugfix |
|---------|-------------------|
| Codebase snapshot | Shows pre-Phase-2 files; doesn't show the code Ralph wrote |
| Architecture references | May reference planned structures that Ralph implemented differently |
| Design specs | Still accurate (specs don't change) |
| Test specs | Still accurate (test expectations don't change) |
| Quality check commands | Still accurate (commands don't change) |
| Codebase patterns | Shows patterns from PREVIOUS milestones only; not from the current one |

### What partially compensates

- `progress.txt` records what Ralph did in Phase 2 (which stories, what learnings)
- The PRD itself was updated by QA with failure notes
- Ralph can read the actual codebase during execution

### Why partial compensation isn't enough

Ralph's CLAUDE.md instructs it to read context.md **first**, treating it as authoritative. If context.md says file X has certain content, but Ralph already modified file X during Phase 2, Ralph has conflicting information:
- context.md says: "file X contains lines 1-50"
- Actual file X: has 200 lines added by Ralph

Ralph must figure out which is current. This wastes iterations on re-exploring the codebase — exactly the waste the context management strategy was designed to prevent.

### Bugfix mode code

In `src/ralph_pipeline/phases/ralph_execution.py`:

```python
def run_ralph_bugfix(
    milestone: MilestoneConfig,
    config: PipelineConfig,
    git: GitOps,
    project_root: Path,
    plogger: PipelineLogger,
    claude: ClaudeRunner | None = None,
    event_logger: EventLogger | None = None,
) -> None:
    """Re-run Ralph in bugfix mode (shorter iteration count)."""
    scripts_dir = project_root / config.paths.scripts_dir
    # ...
    # Re-link PRD (QA updated it with failure notes)
    prd_link = scripts_dir / "prd.json"
    prd_src = project_root / config.paths.tasks_dir / f"prd-m{milestone.id}.json"
    # ...symlink update...

    # Run the same Ralph loop — reads same CLAUDE.md and context.md
    if claude is not None:
        _run_ralph_loop(
            claude=claude,
            scripts_dir=scripts_dir,  # Contains the SAME context.md from Phase 1
            log_dir=log_dir,
            max_iterations=max_iter,
            model=config.models.ralph,
            milestone_id=milestone.id,
            plogger=plogger,
            event_logger=event_logger or EventLogger(log_dir / "pipeline.jsonl"),
        )
```

Notice: PRD is re-linked (QA updated it), but context.md is untouched.

### The QA cycle code

In `src/ralph_pipeline/phases/qa_review.py`:

```python
for cycle in range(0, config.qa.max_bugfix_cycles + 1):
    if cycle > 0:
        # Bugfix: re-run Ralph with updated PRD
        run_ralph_bugfix(milestone, config, git, project_root, plogger, ...)

    # Run QA
    result = test_runner.run_test_suite(...)
    prompt = qa_review_prompt(...)
    claude.run(prompt, ...)
```

No context.md refresh between cycles.

---

## Affected Files

| File | Role |
|------|------|
| `src/ralph_pipeline/phases/ralph_execution.py` | `run_ralph_bugfix()` — uses stale context.md |
| `src/ralph_pipeline/phases/qa_review.py` | QA cycle — no context refresh between cycles |
| `src/ralph_pipeline/phases/prd_generation.py` | Only runs once per milestone (Phase 1) |
| `src/ralph_pipeline/data/skills/prd_writer/SKILL.md` | Defines context bundle assembly |

---

## Impact

- **Severity:** Medium — progress.txt partially compensates, and bugfix cycles are shorter
- **Failure mode:** Wasted iterations — Ralph re-explores what it already changed, or operates on stale assumptions
- **Frequency:** Every bugfix cycle (when QA fails) — typically 1-2 cycles per milestone
- **Blast radius:** Bugfix effectiveness degrades; may fail to fix within the cycle limit

---

## Questions to Consider

1. Should the pipeline refresh the codebase snapshot section of context.md before each bugfix cycle?
2. Should a lightweight "context refresh" function update only the codebase snapshot while keeping architecture/design/test sections?
3. Is a full context.md regeneration (re-invoke PRD Writer) too expensive for a bugfix cycle?
4. Should bugfix mode use a different prompt that tells Ralph "context.md is stale — trust the codebase over the snapshot"?
5. Should progress.txt be restructured to serve as a better secondary context source during bugfix?
6. Could the pipeline append a "bugfix context" section to context.md with QA findings and current codebase state?
