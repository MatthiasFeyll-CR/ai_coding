# Context Management Strategy

How the pipeline manages context to maximize Ralph's code quality while minimizing token waste.

---

## Problem

```
Without context management:

  Ralph Iteration 1          Ralph Iteration 2          Ralph Iteration N
  ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
  │ Read prd.json   │       │ Read prd.json   │       │ Read prd.json   │
  │ Explore docs/   │ ←waste│ Explore docs/   │ ←waste│ Explore docs/   │
  │ Hunt for specs  │       │ Hunt for specs  │       │ Re-read same docs│
  │ Start coding    │       │ Start coding    │       │ Start coding    │
  └─────────────────┘       └─────────────────┘       └─────────────────┘

  Token waste compounds: N stories × M docs explored = wasted context
```

---

## Solution: Three-Layer Context Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  LAYER 1: Planning — Context Weight Sizing                          │
│  (Strategy Planner — runs once during planning phase)               │
│                                                                     │
│  For each milestone, compute context weight:                        │
│  ├─ Unique file paths   (> 30 ⚠)                                   │
│  ├─ Doc sections        (> 5 ⚠)                                    │
│  └─ Story count         (> 10 ⚠)                                   │
│                                                                     │
│  Over threshold? → Split milestone along domain boundaries          │
│  Result: Every milestone fits in Ralph's context window             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  LAYER 2: Generation — Context Bundle                               │
│  (PRD Writer — runs once per milestone in Phase 1)                  │
│                                                                     │
│  Assembles a focused context bundle: .ralph/context.md              │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Source                           What goes in bundle         │  │
│  │  ─────────────────────────────    ─────────────────────────── │  │
│  │  docs/02-architecture/            Relevant tables, endpoints, │  │
│  │    data-model, api-design,        project paths — ONLY        │  │
│  │    project-structure              sections for this milestone │  │
│  │                                                               │  │
│  │  docs/03-design/                  Component specs for this    │  │
│  │                                   milestone's stories         │  │
│  │                                                               │  │
│  │  docs/04-test-architecture/       Test case definitions       │  │
│  │    test-matrix.md                 assigned to this milestone  │  │
│  │                                                               │  │
│  │  .ralph/archive/*/progress.txt    Codebase Patterns section   │  │
│  │                                   ONLY (compressed learnings) │  │
│  │                                                               │  │
│  │  Actual codebase                  File tree + contents of     │  │
│  │                                   files stories will modify   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Rules: only referenced content, verbatim (no summarization),       │
│  fresh per milestone, warns if bundle > ~1500 lines                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  LAYER 3: Consumption — Ralph Reads Context-First                   │
│  (Ralph agent — runs N iterations per milestone in Phase 2)         │
│                                                                     │
│  Ralph's read order (per iteration):                                │
│  1. .ralph/context.md       ← PRIMARY (pre-assembled)               │
│  2. .ralph/prd.json         ← pick next story                      │
│  3. .ralph/progress.txt     ← patterns + recent learnings          │
│  4. docs/*                  ← FALLBACK ONLY                        │
│                                                                     │
│  Result:                                                            │
│  ┌─────────────────┐       ┌─────────────────┐       ┌───────────┐ │
│  │ Read context.md │       │ Read context.md │       │ Read ctx  │ │
│  │ Read prd.json   │       │ Read prd.json   │       │ Read prd  │ │
│  │ Start coding    │       │ Start coding    │       │ Code      │ │
│  └─────────────────┘       └─────────────────┘       └───────────┘ │
│                                                                     │
│  No exploration waste. Same specs every iteration. Consistent code. │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

```
                    PLANNING PHASE
                    ──────────────
docs/02-architecture/ ──┐
docs/03-design/      ──┤      Strategy Planner
docs/04-test-arch/   ──┼────► Context weight check
                        │      Over threshold? → Split milestone
                        │                  │
                        │                  ▼
                        │      docs/05-milestones/milestone-N.md
                        │
                    EXECUTION PHASE
                    ───────────────
                        │
                        ▼
                    ┌────────────────────────────────────┐
                    │  PRD Writer (Phase 1)               │
                    │  Reads: milestone-N.md, all docs,   │
                    │         .ralph/archive/             │
                    │                                     │
                    │  Produces:                           │
                    │  ├─ tasks/prd-mN.json               │
                    │  └─ .ralph/context.md               │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────────────┐
                    │  Ralph (Phase 2)                    │
                    │  Reads:  .ralph/context.md          │
                    │          .ralph/prd.json            │
                    │          .ralph/progress.txt        │
                    │                                     │
                    │  Writes: source code, progress.txt  │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────────────┐
                    │  QA + Merge + Reconcile (Phases 3-4)│
                    │  Archive progress.txt + prd.json    │
                    │  → .ralph/archive/<slug>/           │
                    │  Next milestone starts with clean   │
                    │  context based on updated codebase   │
                    └────────────────────────────────────┘
```
