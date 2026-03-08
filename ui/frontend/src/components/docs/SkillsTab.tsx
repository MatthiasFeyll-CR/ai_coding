import { Badge } from '@/components/shared/Badge';
import clsx from 'clsx';
import { useState } from 'react';

type SkillCategory = 'spec' | 'plan' | 'exec' | 'post';

const CATEGORIES: { id: SkillCategory; label: string; color: string; desc: string }[] = [
  { id: 'spec', label: 'Specification', color: 'bg-accent-cyan', desc: 'Define what to build' },
  { id: 'plan', label: 'Planning', color: 'bg-accent-green', desc: 'How to break it down' },
  { id: 'exec', label: 'Execution', color: 'bg-accent-purple', desc: 'Automated by pipeline' },
  { id: 'post', label: 'Post & Utility', color: 'bg-status-warning', desc: 'After completion' },
];

interface Skill {
  name: string;
  trigger: string;
  output: string;
  desc: string;
  category: SkillCategory;
  invocation: 'Manual' | 'Automated';
  phases?: string;
}

const SKILLS: Skill[] = [
  {
    name: 'Requirements Engineering',
    trigger: '/requirements_engineering',
    output: 'docs/01-requirements/',
    desc: '8-phase structured elicitation: vision, roles, features, pages, data entities, NFRs, constraints. Produces handover.json for the next step.',
    category: 'spec',
    invocation: 'Manual',
  },
  {
    name: 'Software Architect',
    trigger: '/software_architect',
    output: 'docs/02-architecture/',
    desc: '6 phases: tech stack selection, data model design, API design, project structure, testing strategy, handoff.',
    category: 'spec',
    invocation: 'Manual',
  },
  {
    name: 'UI/UX Designer',
    trigger: '/ui_ux_designer',
    output: 'docs/03-design/',
    desc: 'Design system, page layouts (ASCII wireframes), component specs, interaction patterns. Includes design intelligence DB with 67 styles, 96 palettes, 57 font pairings.',
    category: 'spec',
    invocation: 'Manual',
    phases: 'Parallel with AI Engineer',
  },
  {
    name: 'AI Engineer',
    trigger: '/ai_engineer',
    output: 'docs/03-ai/',
    desc: '6 phases: agent architecture, system prompts, tool/function schemas, model config with cost analysis, guardrails.',
    category: 'spec',
    invocation: 'Manual',
    phases: 'Parallel with UI/UX Designer',
  },
  {
    name: 'Arch+AI Integrator',
    trigger: '/arch_ai_integrator',
    output: 'docs/03-integration/',
    desc: '4 phases: gap analysis, bidirectional update, comprehensive audit, handoff. Reconciles architecture and AI docs.',
    category: 'spec',
    invocation: 'Manual',
  },
  {
    name: 'Spec QA',
    trigger: '/spec_qa',
    output: 'docs/04-spec-qa/',
    desc: '5 phases: completeness, cross-reference, consistency, structural soundness. Quality gate: PASS / CONDITIONAL / FAIL.',
    category: 'spec',
    invocation: 'Manual',
  },
  {
    name: 'Test Architect',
    trigger: '/test_architect',
    output: 'docs/04-test-architecture/',
    desc: '6 phases: test plan, test matrix, fixture design, integration scenarios, runtime safety, handoff.',
    category: 'spec',
    invocation: 'Manual',
  },
  {
    name: 'Strategy Planner',
    trigger: '/strategy_planner',
    output: 'docs/05-milestones/',
    desc: 'Dependency analysis, milestone scope files with context-weight validation. Auto-splits oversized milestones along domain boundaries.',
    category: 'plan',
    invocation: 'Manual',
  },
  {
    name: 'Pipeline Configurator',
    trigger: '/pipeline_configurator',
    output: 'pipeline-config.json',
    desc: 'Generates machine-readable config + .ralph/CLAUDE.md. Declares WHAT (declarative test_infrastructure, scaffolding), not HOW. Phase 0 converts to concrete.',
    category: 'plan',
    invocation: 'Manual',
  },
  {
    name: 'PRD Writer',
    trigger: 'Phase 1',
    output: 'tasks/prd-mN.json + .ralph/context.md',
    desc: 'Converts milestone scope into Ralph-consumable PRD with user stories, acceptance criteria, and test specifications. Assembles focused context bundle.',
    category: 'exec',
    invocation: 'Automated',
  },
  {
    name: 'QA Engineer',
    trigger: 'Phase 3',
    output: 'docs/08-qa/qa-mN-slug.md',
    desc: '6-phase review: acceptance criteria, test matrix, quality checks, security, performance, design compliance. Max 3 bugfix cycles then ESCALATE.',
    category: 'exec',
    invocation: 'Automated',
  },
  {
    name: 'Spec Reconciler',
    trigger: 'Phase 4',
    output: 'docs/05-reconciliation/',
    desc: 'Flows implementation deviations back to upstream docs. 3 autonomy levels: SMALL TECHNICAL (auto), FEATURE DESIGN (approval), LARGE TECHNICAL (approval).',
    category: 'exec',
    invocation: 'Automated',
  },
  {
    name: 'Release Engineer',
    trigger: '/release_engineer',
    output: 'docs/09-release/',
    desc: 'Post-pipeline. Generates local deployment documentation after all milestones complete.',
    category: 'post',
    invocation: 'Manual',
  },
  {
    name: 'Pipeline Dashboard',
    trigger: '/pipeline_dashboard',
    output: 'docs/pipeline-status.md',
    desc: 'Utility. Scans all specialist _status.md files and produces a unified pipeline state overview at any time.',
    category: 'post',
    invocation: 'Manual',
  },
];

export function SkillsTab() {
  const [activeCategory, setActiveCategory] = useState<SkillCategory | 'all'>('all');

  const filtered = activeCategory === 'all' ? SKILLS : SKILLS.filter((s) => s.category === activeCategory);

  return (
    <div className="space-y-6">
      {/* Category Toggles */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setActiveCategory('all')}
          className={clsx(
            'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
            activeCategory === 'all'
              ? 'bg-bg-tertiary text-text-primary'
              : 'text-text-muted hover:text-text-primary hover:bg-bg-tertiary'
          )}
        >
          All ({SKILLS.length})
        </button>
        {CATEGORIES.map((c) => {
          const count = SKILLS.filter((s) => s.category === c.id).length;
          return (
            <button
              key={c.id}
              onClick={() => setActiveCategory(c.id)}
              className={clsx(
                'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                activeCategory === c.id
                  ? 'bg-bg-tertiary text-text-primary'
                  : 'text-text-muted hover:text-text-primary hover:bg-bg-tertiary'
              )}
            >
              <div className={`w-2 h-2 rounded-full ${c.color}`} />
              {c.label} ({count})
            </button>
          );
        })}
      </div>

      {/* Skill Count Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {CATEGORIES.map((c) => {
          const count = SKILLS.filter((s) => s.category === c.id).length;
          return (
            <div
              key={c.id}
              className="glass-panel p-4 cursor-pointer hover:bg-bg-tertiary/50 transition-colors"
              onClick={() => setActiveCategory(c.id)}
            >
              <div className="flex items-center gap-2 mb-1">
                <div className={`w-2.5 h-2.5 rounded-full ${c.color}`} />
                <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">{c.label}</span>
              </div>
              <div className="text-2xl font-bold text-text-primary">{count}</div>
              <p className="text-xs text-text-muted">{c.desc}</p>
            </div>
          );
        })}
      </div>

      {/* Skills Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filtered.map((skill) => {
          const cat = CATEGORIES.find((c) => c.id === skill.category)!;
          return (
            <div key={skill.name} className="glass-panel p-5 hover:bg-bg-tertiary/30 transition-colors">
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${cat.color} shrink-0`} />
                  <h4 className="text-sm font-semibold text-text-primary">{skill.name}</h4>
                </div>
                <Badge variant={skill.invocation === 'Automated' ? 'success' : 'info'}>
                  {skill.invocation}
                </Badge>
              </div>
              <p className="text-xs text-text-secondary mb-3">{skill.desc}</p>
              <div className="flex flex-wrap gap-x-4 gap-y-1">
                <div className="flex items-center gap-1">
                  <span className="text-xs text-text-muted">Trigger:</span>
                  <code className="text-xs text-accent-cyan font-mono">{skill.trigger}</code>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-xs text-text-muted">Output:</span>
                  <code className="text-xs text-accent-purple font-mono">{skill.output}</code>
                </div>
                {skill.phases && (
                  <Badge variant="warning">{skill.phases}</Badge>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Handover Chain Visualization */}
      <div className="glass-panel p-6">
        <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Skill Execution Order</h3>
        <p className="text-xs text-text-muted mb-3">
          Each skill produces a <code className="text-accent-purple">handover.json</code> that the next skill consumes. Skills 3a and 3b run in parallel.
        </p>
        <div className="relative">
          <div className="flex flex-wrap items-center gap-2">
            {SKILLS.filter(s => s.category !== 'post').map((skill, i, arr) => (
              <div key={skill.name} className="flex items-center gap-2">
                <div className={clsx(
                  'px-3 py-1.5 rounded-lg text-xs font-medium border',
                  skill.category === 'spec' ? 'bg-accent-cyan/10 border-accent-cyan/30 text-accent-cyan' :
                  skill.category === 'plan' ? 'bg-accent-green/10 border-accent-green/30 text-accent-green' :
                  'bg-accent-purple/10 border-accent-purple/30 text-accent-purple'
                )}>
                  {skill.name.split(' ').map(w => w[0]).join('')}
                </div>
                {i < arr.length - 1 && <span className="text-text-muted text-xs">→</span>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
