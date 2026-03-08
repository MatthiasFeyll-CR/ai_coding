import { Badge } from '@/components/shared/Badge';
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';

const TIER_COMPARISON = [
  { name: 'Tier 1 — Dev', value: 30, color: '#06b6d4', label: '~30×/milestone' },
  { name: 'Tier 2 — Full', value: 3, color: '#a855f7', label: '~3×/milestone' },
];

const ENFORCEMENT_POINTS = [
  { phase: 'Phase 2', point: 'Per-story checks', tier: 'T1', blocking: true, note: 'Ralph self-fixes inline' },
  { phase: 'Phase 3', point: 'QA test run', tier: 'T2', blocking: true, note: 'QA verdict gates milestone completion' },
];

const TEST_ID_PATTERNS = [
  'T-N.N', 'API-N.N', 'DB-N.N', 'UI-N.N', 'LOOP-N', 'STATE-N', 'TIMEOUT-N',
  'LEAK-N', 'INTEGRITY-N', 'AI-SAFE-N', 'SCN-N', 'JOURNEY-N', 'CONC-N', 'ERR-N',
];

const EXTRACTION_TIERS = {
  expected: [
    { tier: '1', method: 'Structured testIds array', quality: 'Deterministic', variant: 'success' as const },
    { tier: '2', method: 'Regex on story notes', quality: 'Fallback', variant: 'warning' as const },
    { tier: '3', method: 'Regex on context.test_cases', quality: 'Fallback', variant: 'warning' as const },
  ],
  found: [
    { tier: '1', method: 'test-manifest.json lookup', quality: 'Deterministic', variant: 'success' as const },
    { tier: '2', method: 'Python AST search', quality: 'Reliable', variant: 'info' as const },
    { tier: '3', method: 'grep across all languages', quality: 'Fallback', variant: 'warning' as const },
  ],
};

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-bg-secondary border border-border-subtle rounded-lg px-3 py-2 shadow-xl">
        <p className="text-xs font-medium text-text-primary">{payload[0].name}</p>
        <p className="text-xs text-text-muted">{payload[0].payload.label}</p>
      </div>
    );
  }
  return null;
};

export function TestingTab() {
  return (
    <div className="space-y-6">
      {/* Two-Tier Visual */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Tier Comparison Chart */}
        <div className="glass-panel p-6">
          <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Execution Frequency</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={TIER_COMPARISON}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={70}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {TIER_COMPARISON.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-col gap-2 mt-2">
            {TIER_COMPARISON.map((t) => (
              <div key={t.name} className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: t.color }} />
                <span className="text-xs text-text-secondary">{t.name}</span>
                <span className="text-xs text-text-muted ml-auto">{t.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Tier 1 Detail */}
        <div className="glass-panel p-6">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-2 h-2 rounded-full bg-accent-cyan" />
            <h3 className="text-sm font-semibold text-text-primary">Tier 1 — Dev Containers</h3>
          </div>
          <div className="space-y-3 text-xs text-text-secondary">
            <p>Docker containers with <strong className="text-text-primary">bind-mounted source code</strong>.</p>
            <p>Fresh containers + volumes per run (clean state).</p>
            <p><strong className="text-accent-cyan">Hash-based rebuild:</strong> MD5 of dependency files tracked in <code className="text-accent-purple">.ralph/.test-image-hashes</code>. Rebuild only when dependencies change.</p>
            <p>On failure: Ralph fixes inline before committing.</p>
          </div>
        </div>

        {/* Tier 2 Detail */}
        <div className="glass-panel p-6">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-2 h-2 rounded-full bg-accent-purple" />
            <h3 className="text-sm font-semibold text-text-primary">Tier 2 — Full Rebuild</h3>
          </div>
          <div className="space-y-3 text-xs text-text-secondary">
            <p>Force teardown → <strong className="text-text-primary">build (no cache)</strong> → setup → health → test.</p>
            <p>Catches <strong className="text-status-warning">stale builds</strong> and <strong className="text-status-warning">contract mismatches</strong>.</p>
            <p>Used during QA phase for maximum confidence.</p>
            <p>On failure: Claude fix cycle → escalation if exhausted.</p>
          </div>
        </div>
      </div>

      {/* Test Coverage Analysis */}
      <div className="glass-panel p-6">
        <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Test Coverage Analysis (Phase 3)</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Extracting Expected IDs */}
          <div>
            <h4 className="text-xs font-semibold text-accent-cyan mb-3">Extracting Expected Test IDs</h4>
            <div className="space-y-2">
              {EXTRACTION_TIERS.expected.map((t) => (
                <div key={t.tier} className="flex items-center gap-3 py-1.5 border-b border-border-subtle/50 last:border-0">
                  <span className="text-xs font-mono text-text-muted w-10">Tier {t.tier}</span>
                  <span className="text-xs text-text-secondary flex-1">{t.method}</span>
                  <Badge variant={t.variant}>{t.quality}</Badge>
                </div>
              ))}
            </div>
          </div>

          {/* Finding Implemented Tests */}
          <div>
            <h4 className="text-xs font-semibold text-accent-purple mb-3">Finding Implemented Tests</h4>
            <div className="space-y-2">
              {EXTRACTION_TIERS.found.map((t) => (
                <div key={t.tier} className="flex items-center gap-3 py-1.5 border-b border-border-subtle/50 last:border-0">
                  <span className="text-xs font-mono text-text-muted w-10">Tier {t.tier}</span>
                  <span className="text-xs text-text-secondary flex-1">{t.method}</span>
                  <Badge variant={t.variant}>{t.quality}</Badge>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Test ID Patterns */}
        <div className="mt-4 pt-4 border-t border-border-subtle">
          <h4 className="text-xs font-semibold text-text-muted mb-2">Recognized Test ID Patterns</h4>
          <div className="flex flex-wrap gap-1.5">
            {TEST_ID_PATTERNS.map((p) => (
              <code key={p} className="text-xs bg-bg-tertiary px-2 py-0.5 rounded text-accent-cyan font-mono">{p}</code>
            ))}
          </div>
        </div>
      </div>

      {/* Regression + Fix Philosophy */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Regression Analysis */}
        <div className="glass-panel p-6">
          <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Regression Analysis</h3>
          <div className="space-y-3">
            {[
              { step: '1', desc: 'After each merge, build_test_map() scans git diff for new test files', color: 'bg-accent-cyan/20 text-accent-cyan' },
              { step: '2', desc: 'Stores {test_file: milestone_id} in state.test_milestone_map', color: 'bg-accent-purple/20 text-accent-purple' },
              { step: '3', desc: 'On failure: parse test files (pytest, jest, vitest, Go patterns)', color: 'bg-status-warning/20 text-status-warning' },
              { step: '4', desc: 'Classify: REGRESSION (owner < current) vs CURRENT', color: 'bg-status-error/20 text-status-error' },
              { step: '5', desc: 'Regressions get targeted prompt with merge diff + archived acceptance criteria', color: 'bg-accent-green/20 text-accent-green' },
            ].map((s) => (
              <div key={s.step} className="flex items-start gap-3">
                <div className={`w-5 h-5 rounded-full ${s.color} flex items-center justify-center text-xs font-mono shrink-0`}>
                  {s.step}
                </div>
                <p className="text-xs text-text-secondary">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Fix Philosophy */}
        <div className="glass-panel p-6">
          <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Fix Philosophy</h3>
          <div className="space-y-4">
            <div className="bg-accent-green/5 border border-accent-green/20 rounded-lg p-3">
              <p className="text-xs font-semibold text-accent-green mb-1">Core Rule</p>
              <p className="text-xs text-text-secondary">Tests are contracts. Fix <strong className="text-text-primary">SOURCE CODE</strong>, not tests.</p>
            </div>
            <div className="space-y-2">
              {[
                { label: 'Previous milestone tests', rule: 'NEVER modified — treated as regression contracts' },
                { label: 'Current milestone tests', rule: 'Modified only if test has a clear bug (wrong import, typo)' },
                { label: 'Domain context', rule: 'Fix prompts include architecture, design, and test specs' },
                { label: 'Audit trail', rule: 'All results stored in docs/08-qa/' },
              ].map((r) => (
                <div key={r.label} className="border-l-2 border-border-emphasis pl-3 py-1">
                  <span className="text-xs font-medium text-text-primary">{r.label}</span>
                  <p className="text-xs text-text-muted">{r.rule}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Enforcement Points */}
      <div className="glass-panel p-6">
        <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Test Enforcement Points</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border-subtle">
                <th className="text-left py-2 pr-6 text-text-muted font-medium">Phase</th>
                <th className="text-left py-2 pr-6 text-text-muted font-medium">Point</th>
                <th className="text-left py-2 pr-6 text-text-muted font-medium">Tier</th>
                <th className="text-left py-2 pr-6 text-text-muted font-medium">Blocking</th>
                <th className="text-left py-2 text-text-muted font-medium">Note</th>
              </tr>
            </thead>
            <tbody>
              {ENFORCEMENT_POINTS.map((e, i) => (
                <tr key={i} className="border-b border-border-subtle/50">
                  <td className="py-2 pr-6 text-text-secondary">{e.phase}</td>
                  <td className="py-2 pr-6 text-text-primary">{e.point}</td>
                  <td className="py-2 pr-6"><Badge variant="info">{e.tier}</Badge></td>
                  <td className="py-2 pr-6">
                    <Badge variant={e.blocking ? 'success' : 'default'}>{e.blocking ? 'Yes' : 'No'}</Badge>
                  </td>
                  <td className="py-2 text-text-muted">{e.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
