import { Badge } from '@/components/shared/Badge';
import {
    Bar,
    BarChart,
    Cell,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

const TRUNCATION_PRIORITY = [
  { section: 'Quality Checks', priority: 9, color: '#10b981' },
  { section: 'Test Infra Setup', priority: 8, color: '#06b6d4' },
  { section: 'Test Specifications', priority: 7, color: '#3b82f6' },
  { section: 'Architecture Ref', priority: 6, color: '#a855f7' },
  { section: 'Design Ref', priority: 5, color: '#7c3aed' },
  { section: 'AI Reference', priority: 4, color: '#f59e0b' },
  { section: 'Browser Testing', priority: 3, color: '#ef4444' },
  { section: 'Codebase Patterns', priority: 2, color: '#6b7280' },
  { section: 'Codebase Snapshot', priority: 1, color: '#374151' },
];

const THRESHOLDS = [
  { metric: 'Unique file paths', threshold: '> 30', action: 'Split milestone' },
  { metric: 'Doc sections', threshold: '> 5', action: 'Split milestone' },
  { metric: 'Story count', threshold: '> 10', action: 'Split milestone' },
];

const BUNDLE_SOURCES = [
  { source: 'docs/02-architecture/', content: 'Relevant tables, endpoints, project paths', scope: 'Milestone-specific' },
  { source: 'docs/03-design/', content: 'Component specs for this milestone\'s stories', scope: 'Story-specific' },
  { source: 'docs/03-ai/', content: 'Agent specs (if applicable)', scope: 'Conditional' },
  { source: 'docs/04-test-architecture/', content: 'Test cases assigned to this milestone', scope: 'Story-specific' },
  { source: '.ralph/archive/', content: 'Codebase patterns (compressed learnings)', scope: 'Accumulated' },
  { source: 'Actual codebase', content: 'File tree + contents of referenced files', scope: 'Dynamic' },
];

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-bg-secondary border border-border-subtle rounded-lg px-3 py-2 shadow-xl">
        <p className="text-xs font-medium text-text-primary">{payload[0].payload.section}</p>
        <p className="text-xs text-text-muted">Priority: {payload[0].value} (higher = kept longer)</p>
      </div>
    );
  }
  return null;
};

export function ContextTab() {
  return (
    <div className="space-y-6">
      {/* Three Layers Visual */}
      <div className="glass-panel p-6">
        <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Three-Layer Context Strategy</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            {
              layer: 'Layer 1',
              name: 'Planning',
              desc: 'Context Weight Sizing',
              detail: 'Strategy Planner computes per-milestone context weight. Over threshold → split milestone.',
              color: 'border-l-accent-cyan bg-accent-cyan/5',
              when: 'Planning phase (once)',
            },
            {
              layer: 'Layer 2',
              name: 'Generation',
              desc: 'Context Bundle',
              detail: 'PRD Writer assembles .ralph/context.md — a focused, milestone-scoped bundle from upstream docs + actual codebase.',
              color: 'border-l-accent-purple bg-accent-purple/5',
              when: 'Phase 1 (per milestone)',
            },
            {
              layer: 'Layer 3',
              name: 'Consumption',
              desc: 'Context-First Reading',
              detail: 'Ralph reads context.md → prd.json → progress.txt. Docs only as fallback. No exploration waste.',
              color: 'border-l-accent-green bg-accent-green/5',
              when: 'Phase 2 (per iteration)',
            },
          ].map((l) => (
            <div key={l.layer} className={`border-l-2 ${l.color} rounded-r-lg p-4`}>
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="info">{l.layer}</Badge>
                <span className="text-sm font-semibold text-text-primary">{l.name}</span>
              </div>
              <p className="text-xs text-accent-cyan font-medium">{l.desc}</p>
              <p className="text-xs text-text-muted mt-2">{l.detail}</p>
              <p className="text-xs text-text-muted mt-2 italic">{l.when}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Two-Column: Weight Thresholds + Bundle Sources */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Weight Thresholds */}
        <div className="glass-panel p-6">
          <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Context Weight Thresholds</h3>
          <p className="text-xs text-text-muted mb-3">If a milestone exceeds any threshold, it should be split along domain boundaries.</p>
          <div className="space-y-2">
            {THRESHOLDS.map((t) => (
              <div key={t.metric} className="flex items-center justify-between py-2 border-b border-border-subtle/50 last:border-0">
                <span className="text-sm text-text-primary">{t.metric}</span>
                <div className="flex items-center gap-3">
                  <code className="text-xs text-status-warning font-mono">{t.threshold}</code>
                  <Badge variant="warning">{t.action}</Badge>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Bundle Sources */}
        <div className="glass-panel p-6">
          <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Context Bundle Sources</h3>
          <p className="text-xs text-text-muted mb-3">The PRD Writer (Phase 1) assembles <code className="text-accent-purple">.ralph/context.md</code> from:</p>
          <div className="space-y-2">
            {BUNDLE_SOURCES.map((b) => (
              <div key={b.source} className="flex items-start gap-2 py-1.5 border-b border-border-subtle/50 last:border-0">
                <code className="text-xs text-accent-cyan font-mono shrink-0 mt-0.5">{b.source}</code>
                <div className="flex-1">
                  <p className="text-xs text-text-secondary">{b.content}</p>
                  <Badge variant="info" className="mt-1">{b.scope}</Badge>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Truncation Priority Chart */}
      <div className="glass-panel p-6">
        <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-2">Truncation Priority</h3>
        <p className="text-xs text-text-muted mb-4">When context exceeds limits, sections are removed from lowest priority first. Higher bars = kept longer.</p>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={TRUNCATION_PRIORITY} layout="vertical" margin={{ left: 20, right: 20 }}>
              <XAxis type="number" domain={[0, 10]} hide />
              <YAxis
                type="category"
                dataKey="section"
                width={120}
                tick={{ fontSize: 11, fill: '#9ca3af' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="priority" radius={[0, 4, 4, 0]} barSize={16}>
                {TRUNCATION_PRIORITY.map((entry) => (
                  <Cell key={entry.section} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Validation + Bugfix */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Validation Flow */}
        <div className="glass-panel p-6">
          <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Validation Flow</h3>
          <div className="space-y-3">
            {[
              { condition: 'Lines > max × warn_pct%', action: 'Warning logged', variant: 'warning' as const },
              { condition: 'Lines > max (1st time)', action: 'Auto-truncate by priority', variant: 'info' as const },
              { condition: 'Lines > max (2nd time)', action: 'ContextOverflowError (abort)', variant: 'error' as const },
            ].map((v) => (
              <div key={v.condition} className="flex items-center justify-between py-2 border-b border-border-subtle/50 last:border-0">
                <code className="text-xs text-text-secondary font-mono">{v.condition}</code>
                <Badge variant={v.variant}>{v.action}</Badge>
              </div>
            ))}
          </div>
          <p className="text-xs text-text-muted mt-3">
            Defaults: max_lines=3000, max_tokens=15000, warn_pct=80
          </p>
        </div>

        {/* Bugfix Context Refresh */}
        <div className="glass-panel p-6">
          <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Bugfix Context Refresh</h3>
          <p className="text-xs text-text-muted mb-3">When QA fails and Ralph enters bugfix mode:</p>
          <div className="space-y-2">
            {[
              { step: '1', desc: 'Strip stale Codebase Snapshot & Bugfix Context sections' },
              { step: '2', desc: 'Rebuild snapshot from actual files (PRD notes → paths, max 200 lines each)' },
              { step: '3', desc: 'Append bugfix context: QA failure summary + git diff stats + fix instructions' },
            ].map((s) => (
              <div key={s.step} className="flex items-start gap-3">
                <div className="w-5 h-5 rounded-full bg-status-warning/20 flex items-center justify-center text-xs font-mono text-status-warning shrink-0">
                  {s.step}
                </div>
                <p className="text-xs text-text-secondary">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Read Order */}
      <div className="glass-panel p-6">
        <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Ralph's Read Order (per iteration)</h3>
        <div className="flex items-center gap-3 overflow-x-auto pb-2">
          {[
            { file: '.ralph/context.md', label: 'PRIMARY', color: 'bg-accent-green/20 border-accent-green/50' },
            { file: '.ralph/prd.json', label: 'STORIES', color: 'bg-accent-cyan/20 border-accent-cyan/50' },
            { file: '.ralph/progress.txt', label: 'LEARNINGS', color: 'bg-accent-purple/20 border-accent-purple/50' },
            { file: 'docs/*', label: 'FALLBACK', color: 'bg-text-muted/20 border-text-muted/50' },
          ].map((f, i) => (
            <div key={f.file} className="flex items-center gap-3 shrink-0">
              <div className={`rounded-lg border px-4 py-3 text-center ${f.color}`}>
                <code className="text-xs font-mono text-text-primary block">{f.file}</code>
                <Badge variant={i === 0 ? 'success' : i === 3 ? 'default' : 'info'} className="mt-1.5">{f.label}</Badge>
              </div>
              {i < 3 && <span className="text-text-muted text-lg">→</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
