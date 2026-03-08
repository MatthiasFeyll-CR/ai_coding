import { Badge } from '@/components/shared/Badge';
import clsx from 'clsx';
import { useState } from 'react';

type PhaseId = '0' | '1' | '2' | '3' | '4';

const PHASES: { id: PhaseId; label: string; name: string; color: string; dotColor: string }[] = [
  { id: '0', label: 'Phase 0', name: 'Bootstrap', color: 'bg-text-muted/10 border-text-muted/30', dotColor: 'bg-text-muted' },
  { id: '1', label: 'Phase 1', name: 'PRD Generation', color: 'bg-accent-purple/10 border-accent-purple/30', dotColor: 'bg-accent-purple' },
  { id: '2', label: 'Phase 2', name: 'Ralph Execution', color: 'bg-accent-cyan/10 border-accent-cyan/30', dotColor: 'bg-accent-cyan' },
  { id: '3', label: 'Phase 3', name: 'QA Review', color: 'bg-status-warning/10 border-status-warning/30', dotColor: 'bg-status-warning' },
  { id: '4', label: 'Phase 4', name: 'Merge + Reconcile', color: 'bg-accent-green/10 border-accent-green/30', dotColor: 'bg-accent-green' },
];

interface PhaseStep {
  action: string;
  detail: string;
}

interface PhaseDetail {
  summary: string;
  steps: PhaseStep[];
  inputs: string[];
  outputs: string[];
  model: string;
  errorHandling: string;
}

const PHASE_DETAILS: Record<PhaseId, PhaseDetail> = {
  '0': {
    summary: 'One-time setup before the milestone loop. Converts declarative specs into verified infrastructure.',
    steps: [
      { action: 'Scaffolding', detail: 'Claude creates project directories + framework boilerplate from architecture docs' },
      { action: 'Test Infra Generation', detail: 'Claude generates docker-compose.test.yml and Dockerfiles from test_infrastructure spec' },
      { action: 'Lifecycle Verification', detail: 'Build → setup → health → smoke → teardown cycle with pass/fail verification report' },
      { action: 'Config Write-Back', detail: 'Generate concrete test_execution commands, remove consumed scaffolding/test_infrastructure sections' },
    ],
    inputs: ['pipeline-config.json [test_infrastructure]', 'pipeline-config.json [scaffolding]', 'Architecture docs'],
    outputs: ['docker-compose.test.yml', 'Dockerfiles', '.ralph/phase0-verification.json', 'Updated pipeline-config.json'],
    model: 'config.models.phase0',
    errorHandling: 'Verification failure → Claude fix loop (max 3) → HARD STOP',
  },
  '1': {
    summary: 'Generate a structured PRD and focused context bundle for the current milestone.',
    steps: [
      { action: 'Check existing PRD', detail: 'If tasks/prd-mN.json exists (resume), skip this phase' },
      { action: 'Load skill + inputs', detail: 'Read PRD Writer skill, milestone scope, archive learnings from prior milestones' },
      { action: 'Inject drift warning', detail: 'Warn if prior milestones have failed reconciliation (stale specs)' },
      { action: 'Generate PRD + Context', detail: 'Claude produces structured JSON PRD + milestone-scoped context bundle' },
      { action: 'Validate bundle', detail: 'Check context size limits; truncate by priority if exceeded' },
      { action: 'Detect domain split', detail: 'If PRD Writer produces domain-split file, halt for re-planning' },
    ],
    inputs: ['docs/05-milestones/milestone-N.md', 'All upstream docs', '.ralph/archive/ learnings'],
    outputs: ['tasks/prd-mN.json', '.ralph/context.md'],
    model: 'config.models.prd_generation',
    errorHandling: 'Retry once → abort milestone. Domain split → HARD STOP (re-plan required)',
  },
  '2': {
    summary: 'Run the iterative Claude coding agent to implement all user stories from the PRD.',
    steps: [
      { action: 'Workspace setup', detail: 'Symlink prd.json, initialize progress.txt, create feature branch ralph/mN-slug' },
      { action: 'Inject runtime footer', detail: 'Append test commands + gate checks to CLAUDE.md (idempotent)' },
      { action: 'Agent loop', detail: 'Budget: stories × multiplier. Each iteration: read CLAUDE.md → invoke Claude → check for COMPLETE signal' },
    ],
    inputs: ['CLAUDE.md', '.ralph/context.md', '.ralph/prd.json', '.ralph/progress.txt'],
    outputs: ['Source code on feature branch', '.ralph/progress.txt (updated)'],
    model: 'config.models.ralph',
    errorHandling: 'Max iterations reached → proceed to QA with partial implementation',
  },
  '3': {
    summary: 'Validate implementation through automated tests, coverage analysis, and AI-powered review.',
    steps: [
      { action: 'Run tests (Tier 2)', detail: 'Full rebuild, fresh services — catches stale builds and contract mismatches' },
      { action: 'Analyze coverage', detail: 'Extract expected test IDs (3-tier) → find implemented tests (3-tier) → FOUND/MISSING report' },
      { action: 'QA review', detail: 'Claude QA Engineer reviews: acceptance criteria, test matrix, results, gates, security, performance' },
      { action: 'Verdict: PASS', detail: 'Archive milestone (PRD + progress) → proceed to Phase 4' },
      { action: 'Verdict: FAIL', detail: 'Refresh context → bugfix mode → Ralph fixes → re-run QA (up to max cycles)' },
    ],
    inputs: ['Test results', 'PRD test IDs', 'Coverage report', 'QA Engineer skill'],
    outputs: ['docs/08-qa/qa-mN-slug.md', 'docs/08-qa/test-results-*.md'],
    model: 'config.models.qa_review',
    errorHandling: 'FAIL after max bugfix cycles → escalation report → continue (best effort)',
  },
  '4': {
    summary: 'Integrate feature branch and update upstream specifications to match reality.',
    steps: [
      { action: 'Merge', detail: 'Commit artifacts, checkout base, tag pre-mN-merge, merge --no-ff' },
      { action: 'Register test ownership', detail: 'build_test_map() scans diff for new test files → state.test_milestone_map' },
      { action: 'Tag + cleanup', detail: 'Tag mN-complete, delete feature branch' },
      { action: 'Deterministic recon', detail: 'Scan doc path references vs actual file tree → drift report (no AI)' },
      { action: 'AI reconciliation', detail: 'Claude Spec Reconciler updates upstream docs. Retry once if changelog not produced.' },
    ],
    inputs: ['Feature branch', 'progress.txt', 'QA report', 'Spec Reconciler skill'],
    outputs: ['Merged code on base', 'docs/05-reconciliation/mN-changes.md', 'mN-deterministic-drift.md', 'Git tags'],
    model: 'config.models.reconciliation',
    errorHandling: 'Merge conflict → abort (should not happen). Reconciliation failure → non-fatal (warn + continue)',
  },
};

const ERRORS = [
  { phase: '0', error: 'Scaffolding / infra generation', action: 'Retry once → HARD STOP', severity: 'error' },
  { phase: '0', error: 'Lifecycle verification', action: 'Claude fix ×3 → HARD STOP', severity: 'error' },
  { phase: '1', error: 'PRD generation', action: 'Retry once → abort milestone', severity: 'error' },
  { phase: '1', error: 'Domain split detected', action: 'HARD STOP (re-plan)', severity: 'error' },
  { phase: '2', error: 'Max iterations reached', action: 'Proceed to QA (partial)', severity: 'warning' },
  { phase: '3', error: 'QA FAIL after max cycles', action: 'Escalation report + continue', severity: 'warning' },
  { phase: '4', error: 'Merge conflict', action: 'Abort (should not happen)', severity: 'error' },
  { phase: '4', error: 'Reconciliation fails', action: 'Retry once → warn + continue', severity: 'warning' },
  { phase: '*', error: 'Claude subprocess crash', action: 'Retry × max_retries', severity: 'warning' },
  { phase: '*', error: 'Cost budget exceeded', action: 'Fatal — no retry', severity: 'error' },
  { phase: '*', error: 'SIGINT / SIGTERM', action: 'Persist state → teardown → exit', severity: 'info' },
];

export function ExecutionTab() {
  const [selectedPhase, setSelectedPhase] = useState<PhaseId>('0');
  const detail = PHASE_DETAILS[selectedPhase];

  return (
    <div className="space-y-6">
      {/* Phase Selector */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {PHASES.map((p) => (
          <button
            key={p.id}
            onClick={() => setSelectedPhase(p.id)}
            className={clsx(
              'flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-all shrink-0',
              selectedPhase === p.id ? p.color : 'border-border-subtle text-text-muted hover:bg-bg-tertiary'
            )}
          >
            <div className={clsx('w-2 h-2 rounded-full', p.dotColor)} />
            <span>{p.label}</span>
            <span className="text-text-muted">—</span>
            <span>{p.name}</span>
          </button>
        ))}
      </div>

      {/* Phase Detail */}
      <div className="glass-panel p-6">
        <p className="text-text-secondary text-sm mb-5">{detail.summary}</p>

        {/* Steps Timeline */}
        <div className="space-y-0">
          {detail.steps.map((step, i) => (
            <div key={i} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div className="w-6 h-6 rounded-full bg-bg-tertiary border border-border-emphasis flex items-center justify-center text-xs font-mono text-text-secondary shrink-0">
                  {i + 1}
                </div>
                {i < detail.steps.length - 1 && <div className="w-px h-full bg-border-subtle min-h-[24px]" />}
              </div>
              <div className="pb-4">
                <span className="text-sm font-semibold text-text-primary">{step.action}</span>
                <p className="text-xs text-text-muted mt-0.5">{step.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* I/O + Model + Error */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-panel p-4">
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Inputs</h4>
          <ul className="space-y-1">
            {detail.inputs.map((inp) => (
              <li key={inp} className="text-xs text-text-secondary flex items-start gap-1.5">
                <span className="text-accent-cyan mt-0.5">→</span> {inp}
              </li>
            ))}
          </ul>
        </div>
        <div className="glass-panel p-4">
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Outputs</h4>
          <ul className="space-y-1">
            {detail.outputs.map((out) => (
              <li key={out} className="text-xs text-text-secondary flex items-start gap-1.5">
                <span className="text-accent-green mt-0.5">←</span> {out}
              </li>
            ))}
          </ul>
        </div>
        <div className="glass-panel p-4">
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Configuration</h4>
          <div className="space-y-2">
            <div>
              <span className="text-xs text-text-muted">Model:</span>
              <code className="text-xs text-accent-purple ml-1">{detail.model}</code>
            </div>
            <div>
              <span className="text-xs text-text-muted">On error:</span>
              <p className="text-xs text-status-warning mt-0.5">{detail.errorHandling}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Error Handling Table */}
      <div className="glass-panel p-6">
        <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Error Handling Matrix</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border-subtle">
                <th className="text-left py-2 pr-4 text-text-muted font-medium">Phase</th>
                <th className="text-left py-2 pr-4 text-text-muted font-medium">Error</th>
                <th className="text-left py-2 text-text-muted font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {ERRORS.map((e, i) => (
                <tr key={i} className="border-b border-border-subtle/50">
                  <td className="py-2 pr-4 font-mono text-text-secondary">{e.phase}</td>
                  <td className="py-2 pr-4 text-text-primary">{e.error}</td>
                  <td className="py-2">
                    <Badge variant={e.severity === 'error' ? 'error' : e.severity === 'warning' ? 'warning' : 'info'}>
                      {e.action}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
