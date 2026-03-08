import { Badge } from '@/components/shared/Badge';
import {
    BoxesIcon,
    CpuIcon,
    DatabaseIcon,
    GitBranchIcon,
    TerminalIcon
} from 'lucide-react';

const TECH_STACK = [
  { name: 'Python 3.11+', desc: 'Runtime & CLI package', icon: TerminalIcon, color: 'text-accent-cyan' },
  { name: 'Pydantic 2.0+', desc: '15+ typed config models', icon: DatabaseIcon, color: 'text-accent-purple' },
  { name: 'transitions', desc: 'FSM milestone phases', icon: BoxesIcon, color: 'text-accent-green' },
  { name: 'Rich', desc: 'Terminal UI & panels', icon: TerminalIcon, color: 'text-status-warning' },
  { name: 'Claude CLI', desc: 'AI agent subprocess', icon: CpuIcon, color: 'text-accent-blue' },
  { name: 'Git', desc: 'Branch-per-milestone VCS', icon: GitBranchIcon, color: 'text-status-error' },
];

const KEY_FEATURES = [
  {
    title: 'Sequential Milestones',
    desc: 'Dependency-aware ordering with automatic phase progression',
    color: 'bg-accent-cyan/10 border-accent-cyan/30',
  },
  {
    title: 'Context Management',
    desc: 'Pre-assembled context bundles eliminate exploration waste',
    color: 'bg-accent-purple/10 border-accent-purple/30',
  },
  {
    title: 'Quality Gates',
    desc: 'Automated tests, coverage analysis, AI-powered QA review',
    color: 'bg-accent-green/10 border-accent-green/30',
  },
  {
    title: 'Spec Alignment',
    desc: 'Post-milestone reconciliation flows deviations back to docs',
    color: 'bg-status-warning/10 border-status-warning/30',
  },
  {
    title: 'Resumable',
    desc: 'State persisted after every phase — resume from any point',
    color: 'bg-accent-blue/10 border-accent-blue/30',
  },
  {
    title: 'Cost Tracking',
    desc: 'Per-invocation token & cost tracking with budget guards',
    color: 'bg-accent-violet/10 border-accent-violet/30',
  },
];

const FSM_STATES = [
  { state: 'pending', color: 'bg-text-muted' },
  { state: 'prd_generation', color: 'bg-accent-purple' },
  { state: 'ralph_execution', color: 'bg-accent-cyan' },
  { state: 'qa_review', color: 'bg-status-warning' },
  { state: 'reconciliation', color: 'bg-accent-green' },
  { state: 'complete', color: 'bg-status-success' },
];

const CLI_COMMANDS = [
  { cmd: 'ralph-pipeline run --config pipeline-config.json', desc: 'Full pipeline run' },
  { cmd: 'ralph-pipeline run --config ... --resume', desc: 'Resume from interruption' },
  { cmd: 'ralph-pipeline run --config ... --milestone 2', desc: 'Start at specific milestone' },
  { cmd: 'ralph-pipeline run --config ... --dry-run', desc: 'Trace without executing' },
  { cmd: 'ralph-pipeline install-skills', desc: 'Install Claude skills' },
  { cmd: 'ralph-pipeline validate-infra --config ...', desc: 'Validate test infrastructure' },
];

export function OverviewTab() {
  return (
    <div className="space-y-6">
      {/* Hero Card */}
      <div className="glass-panel p-6">
        <p className="text-text-secondary leading-relaxed">
          Ralph Pipeline orchestrates multi-milestone software projects using Claude AI agents.
          It takes a project configuration, breaks work into milestones, and drives each through
          a structured lifecycle — from requirements generation to code, QA, and spec reconciliation
          — fully autonomously.
        </p>
      </div>

      {/* Key Features Grid */}
      <div>
        <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-3">Core Capabilities</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {KEY_FEATURES.map((f) => (
            <div key={f.title} className={`rounded-lg border p-4 ${f.color}`}>
              <h4 className="font-semibold text-text-primary text-sm">{f.title}</h4>
              <p className="text-xs text-text-secondary mt-1">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* FSM Visualization */}
      <div className="glass-panel p-6">
        <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Milestone State Machine</h3>
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {FSM_STATES.map((s, i) => (
            <div key={s.state} className="flex items-center gap-2 shrink-0">
              <div className="flex flex-col items-center gap-1.5">
                <div className={`w-3 h-3 rounded-full ${s.color}`} />
                <span className="text-xs text-text-secondary font-mono">{s.state}</span>
              </div>
              {i < FSM_STATES.length - 1 && (
                <div className="w-8 h-px bg-border-emphasis shrink-0 mb-4" />
              )}
            </div>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-2">
          <Badge variant="warning">Bugfix Loop</Badge>
          <span className="text-xs text-text-muted">qa_review → ralph_execution → qa_review (up to max_bugfix_cycles)</span>
        </div>
      </div>

      {/* Two-Column: Tech Stack + CLI */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Tech Stack */}
        <div className="glass-panel p-6">
          <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Tech Stack</h3>
          <div className="space-y-3">
            {TECH_STACK.map((t) => {
              const Icon = t.icon;
              return (
                <div key={t.name} className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${t.color} shrink-0`} />
                  <div>
                    <span className="text-sm font-medium text-text-primary">{t.name}</span>
                    <span className="text-xs text-text-muted ml-2">{t.desc}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* CLI Reference */}
        <div className="glass-panel p-6">
          <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">CLI Commands</h3>
          <div className="space-y-2">
            {CLI_COMMANDS.map((c) => (
              <div key={c.cmd} className="group">
                <code className="text-xs font-mono text-accent-cyan block truncate">{c.cmd}</code>
                <p className="text-xs text-text-muted">{c.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Working Directory */}
      <div className="glass-panel p-6">
        <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Working Directory (.ralph/)</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-1.5">
          {[
            { file: 'state.json', desc: 'FSM state, cost tracking, test ownership' },
            { file: 'pipeline.lock', desc: 'PID-based lock (concurrent prevention)' },
            { file: 'prd.json', desc: 'Symlink to active milestone PRD' },
            { file: 'context.md', desc: 'Context bundle for current milestone' },
            { file: 'progress.txt', desc: 'Agent progress & learnings' },
            { file: 'CLAUDE.md', desc: 'Agent instructions + runtime footer' },
            { file: 'logs/pipeline.jsonl', desc: 'Structured event log' },
            { file: 'archive/<slug>/', desc: 'Archived PRDs & progress' },
          ].map((f) => (
            <div key={f.file} className="flex items-baseline gap-2 py-1">
              <code className="text-xs font-mono text-accent-purple shrink-0">{f.file}</code>
              <span className="text-xs text-text-muted">{f.desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
