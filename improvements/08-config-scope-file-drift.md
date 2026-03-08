# Issue 08: pipeline-config.json and milestone-N.md Can Drift

## Instructions for AI

You are a professional AI engineer reviewing a pipeline orchestration system. Your role:

1. **Understand** the problem described below fully. Ask clarifying questions if anything is unclear.
2. **Recommend** concrete improvements with trade-offs. Discuss alternatives.
3. **Do NOT implement** anything until the user explicitly says to proceed.
4. **Ask questions** about edge cases, scope, and priorities before proposing solutions.

Read the referenced files to get full context before making recommendations.

---

## System Overview

Ralph Pipeline uses two separate artifacts to define milestones:

1. **`pipeline-config.json`** — machine-readable config with milestone metadata:
   ```json
   {
     "milestones": [
       { "id": 1, "slug": "foundation", "name": "Foundation", "stories": 3 }
     ]
   }
   ```

2. **`docs/05-milestones/milestone-N.md`** — human-readable scope file with full feature descriptions, story outlines, architecture references, test IDs, and acceptance criteria.

These two artifacts are produced by different steps (Pipeline Configurator writes config, Strategy Planner writes scope files) and are never cross-validated.

---

## The Problem

The `stories` count in `pipeline-config.json` directly controls Ralph's iteration budget:

```python
# From src/ralph_pipeline/phases/ralph_execution.py, line 153:
max_iter = milestone.stories * config.ralph.max_iterations_multiplier
```

With default `max_iterations_multiplier = 3`, a milestone with `stories: 5` gets 15 iterations. If the actual scope file describes 8 stories but the config says 5, Ralph gets 15 iterations instead of 24.

### How drift happens

1. **Post-planning edits:** User or AI edits `milestone-N.md` to add/remove stories without updating `pipeline-config.json`
2. **PRD Writer generates more stories:** The PRD Writer reads `milestone-N.md` and breaks features into more stories than the scope file outlined (right-sizing for Ralph iterations)
3. **Reconciliation adds scope:** After milestone N, spec reconciliation may update scope files for milestone N+1 without touching the config
4. **Strategy Planner counts differently:** The "story outline" in milestone-N.md might list 7 bullets but the Strategy Planner told the Configurator "5 stories" because some bullets are sub-tasks

### What the config knows about milestones

From `src/ralph_pipeline/config.py`:

```python
class MilestoneConfig(BaseModel):
    id: int
    slug: str
    name: str
    stories: int
    dependencies: list[int] = []
```

Only 5 fields. The actual scope, feature list, architecture references, and test IDs live solely in the scope files. No cross-reference.

### No validation exists

There is no code that:
- Reads `milestone-N.md` and counts outlined stories
- Compares the count to `config.milestones[N].stories`
- Checks that `milestone-N.md` exists for every configured milestone
- Checks that every `milestone-N.md` has a corresponding config entry

---

## Affected Files

| File | Role |
|------|------|
| `src/ralph_pipeline/config.py` | `MilestoneConfig` — `stories` field controls iteration budget |
| `src/ralph_pipeline/phases/ralph_execution.py` | `max_iter = milestone.stories * multiplier` |
| `src/ralph_pipeline/data/skills/strategy_planner/SKILL.md` | Produces milestone scope files |
| `src/ralph_pipeline/data/skills/pipeline_configurator/SKILL.md` | Produces pipeline-config.json from strategy handover |
| `src/ralph_pipeline/runner.py` | Main loop iterates over `config.milestones` |

---

## Impact

- **Severity:** Medium — wrong iteration budget means Ralph either runs out of iterations too early or wastes iterations
- **Failure mode:** Silent — too few iterations means Ralph hits MAX_ITERATIONS and proceeds to QA with incomplete work; too many iterations wastes time/tokens
- **Frequency:** Likely after manual edits or reconciliation updates
- **Blast radius:** Affects one milestone's Phase 2 execution

---

## Questions to Consider

1. Should the pipeline validate that `milestone-N.md` exists for every milestone in the config before starting execution?
2. Should the `stories` count be derived from the PRD (after Phase 1) rather than from the config? The PRD has the actual story count.
3. Should `max_iterations` be recalculated after PRD generation using the actual story count from `prd-mN.json`?
4. Should the config store a hash or checksum of the scope file to detect drift?
5. Is the `stories` field in the config even necessary, or should it be a Phase 1 output?
6. Should there be a `validate-config` CLI command that checks scope file alignment before running the pipeline?
