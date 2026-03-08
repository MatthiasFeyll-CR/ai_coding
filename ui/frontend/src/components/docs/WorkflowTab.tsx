import { Badge } from '@/components/shared/Badge';

const SPEC_STEPS = [
  {
    num: '1',
    name: 'Requirements Engineering',
    output: 'docs/01-requirements/',
    desc: '8-phase structured elicitation: vision, roles, features, pages, data, NFRs, constraints',
    color: 'border-l-accent-cyan',
  },
  {
    num: '2',
    name: 'Software Architect',
    output: 'docs/02-architecture/',
    desc: 'Tech stack, data model, API design, project structure, testing strategy',
    color: 'border-l-accent-blue',
  },
  {
    num: '3a',
    name: 'UI/UX Designer',
    output: 'docs/03-design/',
    desc: 'Design system, ASCII wireframes, component specs, interaction patterns',
    color: 'border-l-accent-purple',
    parallel: true,
  },
  {
    num: '3b',
    name: 'AI Engineer',
    output: 'docs/03-ai/',
    desc: 'Agent architecture, system prompts, tool schemas, model selection, guardrails',
    color: 'border-l-accent-purple',
    parallel: true,
  },
  {
    num: '3c',
    name: 'Arch+AI Integrator',
    output: 'docs/03-integration/',
    desc: 'Gap analysis, bidirectional update, comprehensive audit between architecture & AI',
    color: 'border-l-accent-violet',
  },
  {
    num: '4',
    name: 'Spec QA',
    output: 'docs/04-spec-qa/',
    desc: 'Completeness, cross-reference, consistency checks → PASS / CONDITIONAL / FAIL',
    color: 'border-l-status-warning',
  },
  {
    num: '4b',
    name: 'Test Architect',
    output: 'docs/04-test-architecture/',
    desc: 'Test plan, test matrix, fixture design, integration scenarios, runtime safety',
    color: 'border-l-status-warning',
  },
];

const PLAN_STEPS = [
  {
    num: '5',
    name: 'Strategy Planner',
    output: 'docs/05-milestones/',
    desc: 'Dependency analysis, milestone scope files with context-weight validation, auto-splits oversized milestones',
    color: 'border-l-accent-green',
  },
  {
    num: '6',
    name: 'Pipeline Configurator',
    output: 'pipeline-config.json',
    desc: 'Machine-readable config with declarative test_infrastructure + scaffolding specs',
    color: 'border-l-accent-green',
  },
];

const EXEC_PHASES = [
  { label: 'Phase 0', desc: 'Bootstrap', detail: 'Scaffolding + test infra + lifecycle verification', color: 'bg-text-muted' },
  { label: 'Phase 1', desc: 'PRD Generation', detail: 'Structured PRD + context bundle per milestone', color: 'bg-accent-purple' },
  { label: 'Phase 2', desc: 'Ralph Coding', detail: 'Iterative Claude sessions on feature branch', color: 'bg-accent-cyan' },
  { label: 'Phase 3', desc: 'QA Review', detail: 'Tests + coverage + AI review + bugfix cycles', color: 'bg-status-warning' },
  { label: 'Phase 4', desc: 'Merge + Reconcile', detail: 'Merge, tag, register tests, update docs', color: 'bg-accent-green' },
];

export function WorkflowTab() {
  return (
    <div className="space-y-6">
      {/* Visual Pipeline Flow */}
      <div className="glass-panel p-6">
        <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">
          End-to-End Pipeline Flow
        </h3>

        {/* Four macro-phases as horizontal flow */}
        <div className="flex items-stretch gap-3 overflow-x-auto pb-2">
          {[
            { label: 'SPECIFICATION', color: 'bg-accent-cyan/10 border-accent-cyan/30', badge: 'Manual', variant: 'info' as const },
            { label: 'PLANNING', color: 'bg-accent-green/10 border-accent-green/30', badge: 'Manual', variant: 'success' as const },
            { label: 'EXECUTION', color: 'bg-accent-purple/10 border-accent-purple/30', badge: 'Automated', variant: 'warning' as const },
            { label: 'RELEASE', color: 'bg-status-warning/10 border-status-warning/30', badge: 'Manual', variant: 'info' as const },
          ].map((phase, i) => (
            <div key={phase.label} className="flex items-center gap-3 shrink-0">
              <div className={`rounded-lg border p-4 min-w-[140px] text-center ${phase.color}`}>
                <div className="text-xs font-bold tracking-wider text-text-primary">{phase.label}</div>
                <Badge variant={phase.variant} className="mt-2">{phase.badge}</Badge>
              </div>
              {i < 3 && <div className="text-text-muted text-lg">→</div>}
            </div>
          ))}
        </div>
      </div>

      {/* Two-Column: Spec + Planning */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Specification Phase */}
        <div className="glass-panel p-6">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-2 h-2 rounded-full bg-accent-cyan" />
            <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider">Specification Phase</h3>
          </div>
          <div className="space-y-2">
            {SPEC_STEPS.map((s) => (
              <div
                key={s.num}
                className={`border-l-2 ${s.color} pl-3 py-2`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-text-muted w-5">{s.num}</span>
                  <span className="text-sm font-medium text-text-primary">{s.name}</span>
                  {s.parallel && <Badge variant="info">parallel</Badge>}
                </div>
                <p className="text-xs text-text-muted mt-0.5 ml-7">{s.desc}</p>
                <code className="text-xs text-accent-purple ml-7">{s.output}</code>
              </div>
            ))}
          </div>
        </div>

        {/* Planning Phase */}
        <div className="space-y-6">
          <div className="glass-panel p-6">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-2 h-2 rounded-full bg-accent-green" />
              <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider">Planning Phase</h3>
            </div>
            <div className="space-y-2">
              {PLAN_STEPS.map((s) => (
                <div key={s.num} className={`border-l-2 ${s.color} pl-3 py-2`}>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-text-muted w-5">{s.num}</span>
                    <span className="text-sm font-medium text-text-primary">{s.name}</span>
                  </div>
                  <p className="text-xs text-text-muted mt-0.5 ml-7">{s.desc}</p>
                  <code className="text-xs text-accent-purple ml-7">{s.output}</code>
                </div>
              ))}
            </div>
          </div>

          {/* Execution Phase Summary */}
          <div className="glass-panel p-6">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-2 h-2 rounded-full bg-accent-purple" />
              <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider">Execution Phase</h3>
            </div>
            <div className="space-y-2">
              {EXEC_PHASES.map((p) => (
                <div key={p.label} className="flex items-start gap-3 py-1.5">
                  <div className={`w-2.5 h-2.5 rounded-full ${p.color} mt-1 shrink-0`} />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-text-primary">{p.label}</span>
                      <span className="text-xs text-text-secondary">{p.desc}</span>
                    </div>
                    <p className="text-xs text-text-muted">{p.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Handover Chain */}
      <div className="glass-panel p-6">
        <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Handover Chain</h3>
        <p className="text-xs text-text-muted mb-3">
          Each skill produces a <code className="text-accent-purple">handover.json</code> consumed by the next skill in the chain.
        </p>
        <div className="flex items-center gap-1.5 overflow-x-auto pb-2">
          {[
            '01-requirements',
            '02-architecture',
            '03-design | 03-ai',
            '03-integration',
            '04-spec-qa',
            '04-test-arch',
            '05-milestones',
            '.ralph/',
            'Pipeline Run',
          ].map((name, i) => (
            <div key={name} className="flex items-center gap-1.5 shrink-0">
              <div className="px-2 py-1 bg-bg-tertiary rounded text-xs font-mono text-text-secondary whitespace-nowrap">
                {name}
              </div>
              {i < 8 && <span className="text-text-muted text-xs">→</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
