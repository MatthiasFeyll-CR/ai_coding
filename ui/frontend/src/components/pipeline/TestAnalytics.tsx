import { pipelineApi } from '@/api/client';
import type { MilestoneTestAnalytics, TestAnalytics as TestAnalyticsData } from '@/types';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
    BeakerIcon,
    CheckCircle2Icon,
    FileWarningIcon,
    ShieldCheckIcon,
    TrendingUpIcon,
    WrenchIcon,
    XCircleIcon
} from 'lucide-react';
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Legend,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

interface TestAnalyticsProps {
  projectId?: number;
}

// ── Color palette ───────────────────────────────────────────────────────────

const CHART_COLORS = ['#06b6d4', '#a855f7', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#14b8a6'];
const STATUS_GREEN = '#10b981';
const STATUS_RED = '#ef4444';
const STATUS_AMBER = '#f59e0b';
const STATUS_MUTED = '#6b7280';

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatDuration(seconds: number): string {
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}m ${secs.toFixed(0)}s`;
}

function formatPercent(pct: number): string {
  return `${pct.toFixed(1)}%`;
}

function verdictColor(verdict: string): string {
  if (verdict === 'PASS') return STATUS_GREEN;
  if (verdict === 'FAIL') return STATUS_RED;
  return STATUS_MUTED;
}

function verdictVariant(verdict: string): 'success' | 'error' | 'warning' | 'default' {
  if (verdict === 'PASS') return 'success';
  if (verdict === 'FAIL') return 'error';
  if (verdict === 'pending') return 'warning';
  return 'default';
}

// ── KPI Card ────────────────────────────────────────────────────────────────

interface KpiCardProps {
  label: string;
  value: string;
  subtitle?: string;
  icon: React.ReactNode;
  accentClass: string;
}

function KpiCard({ label, value, subtitle, icon, accentClass }: KpiCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-bg-secondary rounded-xl border border-border-subtle p-5 relative overflow-hidden transition-shadow"
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-text-muted text-sm font-medium uppercase tracking-wider">{label}</p>
          <p className={`text-2xl font-bold ${accentClass}`}>{value}</p>
          {subtitle && <p className="text-text-muted text-sm">{subtitle}</p>}
        </div>
        <div className={`p-2.5 rounded-lg bg-bg-tertiary ${accentClass}`}>
          {icon}
        </div>
      </div>
    </motion.div>
  );
}

// ── Chart Card ──────────────────────────────────────────────────────────────

interface ChartCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}

function ChartCard({ title, subtitle, children, className }: ChartCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`bg-bg-secondary rounded-xl border border-border-subtle p-5 ${className ?? ''}`}
    >
      <div className="mb-4">
        <h3 className="text-base font-semibold text-text-primary">{title}</h3>
        {subtitle && <p className="text-sm text-text-muted mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </motion.div>
  );
}

// ── Badge ───────────────────────────────────────────────────────────────────

function StatusBadge({ variant, children }: { variant: 'success' | 'error' | 'warning' | 'default'; children: React.ReactNode }) {
  const classes: Record<string, string> = {
    success: 'bg-status-success/20 text-status-success',
    error: 'bg-status-error/20 text-status-error',
    warning: 'bg-status-warning/20 text-status-warning',
    default: 'bg-bg-tertiary text-text-secondary',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wide ${classes[variant]}`}>
      {children}
    </span>
  );
}

// ── Tooltip styling ─────────────────────────────────────────────────────────

const tooltipStyle = {
  backgroundColor: '#111827',
  border: '1px solid #374151',
  borderRadius: '8px',
  fontSize: '13px',
  boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
};

// ── Main Component ──────────────────────────────────────────────────────────

export function TestAnalytics({ projectId }: TestAnalyticsProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['test-analytics', projectId],
    queryFn: () => pipelineApi.getTestAnalytics(projectId!).then((res) => res.data),
    enabled: !!projectId,
    refetchInterval: 5000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-text-muted">
          <div className="w-5 h-5 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
          Loading test analytics...
        </div>
      </div>
    );
  }

  if (!data || (data.summary.total_test_runs === 0 && data.milestones.length === 0 && data.qa_reports.length === 0)) {
    return (
      <div className="relative">
        {/* Placeholder skeleton layout */}
        <div className="space-y-6 pointer-events-none select-none">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {['Pass Rate', 'Test Runs', 'Fix Cycles', 'QA First Pass'].map((label) => (
              <div key={label} className="bg-bg-secondary rounded-xl border border-border-subtle p-5">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-9 h-9 rounded-lg bg-bg-tertiary" />
                  <span className="text-xs text-text-muted uppercase tracking-wider">{label}</span>
                </div>
                <div className="h-8 w-16 bg-bg-tertiary rounded" />
                <div className="h-3 w-28 bg-bg-tertiary rounded mt-2" />
              </div>
            ))}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="bg-bg-secondary rounded-xl border border-border-subtle p-5 lg:col-span-2">
              <div className="h-4 w-40 bg-bg-tertiary rounded mb-4" />
              <div className="h-[240px] bg-bg-tertiary/50 rounded" />
            </div>
            <div className="bg-bg-secondary rounded-xl border border-border-subtle p-5">
              <div className="h-4 w-32 bg-bg-tertiary rounded mb-4" />
              <div className="h-[240px] bg-bg-tertiary/50 rounded" />
            </div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-bg-secondary rounded-xl border border-border-subtle p-5">
              <div className="h-4 w-36 bg-bg-tertiary rounded mb-4" />
              <div className="h-[200px] bg-bg-tertiary/50 rounded" />
            </div>
            <div className="bg-bg-secondary rounded-xl border border-border-subtle p-5">
              <div className="h-4 w-36 bg-bg-tertiary rounded mb-4" />
              <div className="h-[200px] bg-bg-tertiary/50 rounded" />
            </div>
          </div>
        </div>
        {/* Overlay */}
        <div className="absolute inset-0 flex items-center justify-center z-10">
          <div className="bg-bg-secondary/70 backdrop-blur-sm border border-border-subtle rounded-2xl px-10 py-8 flex flex-col items-center text-center shadow-xl max-w-md">
            <BeakerIcon className="w-10 h-10 text-text-muted mb-3 opacity-60" />
            <h3 className="text-base font-semibold text-text-primary mb-1">No Test Data Available</h3>
            <p className="text-text-muted text-sm leading-relaxed">
              Test analytics will appear here once the pipeline runs QA phases.
              Data is collected from pipeline event logs and QA result files.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const { summary, milestones, top_failing_files, qa_reports } = data;

  // Use qa_reports as fallback data when pipeline.jsonl events are not yet available
  const hasEventData = summary.total_test_runs > 0;

  // Derive metrics from qa_reports if no event data exists
  const effectiveSummary = hasEventData ? summary : deriveFromReports(qa_reports, milestones, summary);

  return (
    <div className="space-y-6">
      {/* ── KPI Cards ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Pass Rate"
          value={formatPercent(effectiveSummary.pass_rate)}
          subtitle={`${effectiveSummary.passed} passed · ${effectiveSummary.failed} failed`}
          icon={<ShieldCheckIcon className="w-5 h-5" />}
          accentClass={effectiveSummary.pass_rate >= 80 ? 'text-status-success' : effectiveSummary.pass_rate >= 50 ? 'text-status-warning' : 'text-status-error'}
        />
        <KpiCard
          label="Test Runs"
          value={String(effectiveSummary.total_test_runs)}
          subtitle={`across ${milestones.length} milestone${milestones.length !== 1 ? 's' : ''}`}
          icon={<BeakerIcon className="w-5 h-5" />}
          accentClass="text-accent-cyan"
        />
        <KpiCard
          label="Fix Cycles"
          value={String(effectiveSummary.total_fix_cycles)}
          subtitle={`${effectiveSummary.total_bugfix_cycles} bugfix · ${effectiveSummary.total_test_fix_cycles} test-fix`}
          icon={<WrenchIcon className="w-5 h-5" />}
          accentClass={effectiveSummary.total_fix_cycles > 0 ? 'text-status-warning' : 'text-status-success'}
        />
        <KpiCard
          label="QA First Pass"
          value={`${effectiveSummary.qa_first_pass_count}/${milestones.filter(m => m.final_verdict !== 'pending').length}`}
          subtitle={effectiveSummary.qa_first_pass_count === milestones.filter(m => m.final_verdict !== 'pending').length ? 'All passed first try' : 'Some needed bugfixes'}
          icon={<TrendingUpIcon className="w-5 h-5" />}
          accentClass="text-accent-purple"
        />
      </div>

      {/* ── Row 1: Milestone Breakdown Table + Pass/Fail by Milestone Chart ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Milestone Test Breakdown — Full-width table */}
        <ChartCard
          title="Test Results by Milestone"
          subtitle="Per-milestone test execution, verdicts, and fix cycles"
          className="lg:col-span-2"
        >
          <MilestoneTable milestones={milestones} maxBugfixCycles={effectiveSummary.max_bugfix_cycles} />
        </ChartCard>

        {/* Pass/Fail Donut */}
        <ChartCard title="Overall Pass / Fail" subtitle="All test runs combined">
          <PassFailDonut passed={effectiveSummary.passed} failed={effectiveSummary.failed} />
        </ChartCard>
      </div>

      {/* ── Row 2: Fix Cycles per Milestone + Top Failing Files ──────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Fix Cycles Bar Chart */}
        <ChartCard title="Fix Cycles per Milestone" subtitle="Bugfix and test-fix cycles needed">
          <FixCyclesChart milestones={milestones} />
        </ChartCard>

        {/* Top Failing Files */}
        <ChartCard
          title="Most Frequently Failing Files"
          subtitle={top_failing_files.length > 0 ? `Top ${top_failing_files.length} by failure count` : 'No failures detected'}
        >
          {top_failing_files.length > 0 ? (
            <div className="overflow-auto max-h-[280px]">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-bg-secondary">
                  <tr className="text-text-muted border-b border-border-subtle">
                    <th className="text-left py-2 pr-3 font-medium">File</th>
                    <th className="text-right py-2 pl-2 font-medium">Failures</th>
                    <th className="text-left py-2 pl-3 font-medium w-32">Frequency</th>
                  </tr>
                </thead>
                <tbody>
                  {top_failing_files.map((f) => {
                    const maxFails = top_failing_files[0]?.failures || 1;
                    const pct = (f.failures / maxFails) * 100;
                    return (
                      <tr key={f.file} className="border-b border-border-subtle/50 hover:bg-bg-tertiary/50">
                        <td className="py-2 pr-3">
                          <div className="flex items-center gap-2">
                            <FileWarningIcon className="w-3 h-3 text-status-error flex-shrink-0" />
                            <span className="text-text-primary font-mono text-xs truncate max-w-[200px]" title={f.file}>
                              {f.file.split('/').pop()}
                            </span>
                          </div>
                        </td>
                        <td className="text-right py-2 pl-2 text-status-error font-mono font-semibold">
                          {f.failures}
                        </td>
                        <td className="py-2 pl-3">
                          <div className="w-full bg-bg-tertiary rounded-full h-1.5">
                            <div
                              className="bg-status-error/70 h-1.5 rounded-full transition-all"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="h-[200px] flex flex-col items-center justify-center text-text-muted">
              <CheckCircle2Icon className="w-8 h-8 mb-2 text-status-success/60" />
              <p className="text-sm">No failing test files detected</p>
            </div>
          )}
        </ChartCard>
      </div>

      {/* ── Row 3: QA Report History ─────────────────────────────────────── */}
      {qa_reports.length > 0 && (
        <ChartCard
          title="QA Test Run History"
          subtitle={`${qa_reports.length} test execution${qa_reports.length !== 1 ? 's' : ''} recorded`}
        >
          <QaReportTimeline reports={qa_reports} milestones={milestones} />
        </ChartCard>
      )}
    </div>
  );
}

// ── Derive summary from QA report files when event data is absent ───────────

function deriveFromReports(
  reports: TestAnalyticsData['qa_reports'],
  milestones: MilestoneTestAnalytics[],
  fallback: TestAnalyticsData['summary'],
): TestAnalyticsData['summary'] {
  if (reports.length === 0) return fallback;

  const passed = reports.filter(r => r.passed).length;
  const failed = reports.length - passed;
  const passRate = reports.length > 0 ? (passed / reports.length) * 100 : 0;

  const totalBugfix = milestones.reduce((s, m) => s + m.bugfix_cycles, 0);
  const totalTestFix = milestones.reduce((s, m) => s + m.test_fix_cycles, 0);

  // Count milestones with first-pass (only cycle 0 passed)
  const milestoneCycle0: Map<number, boolean> = new Map();
  for (const r of reports) {
    if (r.cycle === 0 && r.passed) {
      milestoneCycle0.set(r.milestone, true);
    }
  }

  return {
    total_test_runs: reports.length,
    passed,
    failed,
    pass_rate: Math.round(passRate * 10) / 10,
    total_fix_cycles: totalBugfix + totalTestFix,
    total_bugfix_cycles: totalBugfix,
    total_test_fix_cycles: totalTestFix,
    avg_duration_s: fallback.avg_duration_s,
    total_test_time_s: fallback.total_test_time_s,
    qa_pass_count: milestones.filter(m => m.final_verdict === 'PASS').length,
    qa_fail_count: milestones.filter(m => m.final_verdict === 'FAIL').length,
    qa_first_pass_count: milestoneCycle0.size,
    max_bugfix_cycles: fallback.max_bugfix_cycles,
  };
}

// ── Milestone Table ─────────────────────────────────────────────────────────

function MilestoneTable({ milestones, maxBugfixCycles }: { milestones: MilestoneTestAnalytics[]; maxBugfixCycles: number }) {
  if (milestones.length === 0) {
    return (
      <div className="h-[200px] flex items-center justify-center text-text-muted text-sm">
        No milestone data available
      </div>
    );
  }

  return (
    <div className="overflow-auto max-h-[320px]">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-bg-secondary">
          <tr className="text-text-muted border-b border-border-subtle">
            <th className="text-left py-2 pr-3 font-medium">Milestone</th>
            <th className="text-center py-2 px-2 font-medium">Phase</th>
            <th className="text-center py-2 px-2 font-medium">Verdict</th>
            <th className="text-right py-2 px-2 font-medium">Runs</th>
            <th className="text-right py-2 px-2 font-medium">Pass Rate</th>
            <th className="text-center py-2 px-2 font-medium">Bugfix</th>
            <th className="text-right py-2 pl-2 font-medium">Duration</th>
          </tr>
        </thead>
        <tbody>
          {milestones.map((m) => (
            <tr key={m.id} className="border-b border-border-subtle/50 hover:bg-bg-tertiary/50 transition-colors">
              <td className="py-2.5 pr-3">
                <div className="flex items-center gap-2">
                  <span className="text-text-muted font-mono text-xs">M{m.id}</span>
                  <span className="text-text-primary font-medium">{m.name}</span>
                  {m.first_pass && (
                    <span title="Passed QA on first attempt" className="text-status-success">
                      <CheckCircle2Icon className="w-3 h-3" />
                    </span>
                  )}
                </div>
              </td>
              <td className="text-center py-2.5 px-2">
                <StatusBadge variant={m.phase === 'complete' ? 'success' : m.phase === 'failed' ? 'error' : 'default'}>
                  {m.phase}
                </StatusBadge>
              </td>
              <td className="text-center py-2.5 px-2">
                <StatusBadge variant={verdictVariant(m.final_verdict)}>
                  {m.final_verdict}
                </StatusBadge>
              </td>
              <td className="text-right py-2.5 px-2 text-text-secondary font-mono">
                {m.test_runs || '—'}
              </td>
              <td className="text-right py-2.5 px-2">
                {m.test_runs > 0 ? (
                  <span className={m.pass_rate >= 80 ? 'text-status-success' : m.pass_rate >= 50 ? 'text-status-warning' : 'text-status-error'}>
                    {formatPercent(m.pass_rate)}
                  </span>
                ) : (
                  <span className="text-text-muted">—</span>
                )}
              </td>
              <td className="text-center py-2.5 px-2">
                <BugfixIndicator cycles={m.bugfix_cycles} max={maxBugfixCycles} />
              </td>
              <td className="text-right py-2.5 pl-2 text-text-secondary font-mono">
                {m.total_duration_s > 0 ? formatDuration(m.total_duration_s) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Bugfix dot indicator ────────────────────────────────────────────────────

function BugfixIndicator({ cycles, max }: { cycles: number; max: number }) {
  if (cycles === 0) {
    return <span className="text-text-muted text-xs">0</span>;
  }

  return (
    <div className="flex items-center justify-center gap-0.5">
      {Array.from({ length: max }, (_, i) => (
        <div
          key={i}
          className={`w-2 h-2 rounded-full ${
            i < cycles
              ? cycles >= max ? 'bg-status-error' : 'bg-status-warning'
              : 'bg-bg-tertiary'
          }`}
          title={i < cycles ? `Cycle ${i + 1}` : 'Unused'}
        />
      ))}
      <span className="ml-1 text-xs text-text-muted font-mono">{cycles}</span>
    </div>
  );
}

// ── Pass/Fail Donut ─────────────────────────────────────────────────────────

function PassFailDonut({ passed, failed }: { passed: number; failed: number }) {
  const total = passed + failed;
  if (total === 0) {
    return (
      <div className="h-[240px] flex items-center justify-center text-text-muted text-sm">
        No test data
      </div>
    );
  }

  const data = [
    { name: 'Passed', value: passed },
    { name: 'Failed', value: failed },
  ].filter(d => d.value > 0);

  const colors = [STATUS_GREEN, STATUS_RED];

  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={55}
          outerRadius={85}
          paddingAngle={4}
          dataKey="value"
          strokeWidth={0}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={colors[i]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value: number, name: string) => [
            `${value} (${((value / total) * 100).toFixed(1)}%)`,
            name,
          ]}
        />
        <Legend
          wrapperStyle={{ fontSize: '13px' }}
          formatter={(value) => <span className="text-text-secondary">{value}</span>}
        />
        <text x="50%" y="47%" textAnchor="middle" fill="#f9fafb" fontSize="22" fontWeight="bold">
          {formatPercent(total > 0 ? (passed / total) * 100 : 0)}
        </text>
        <text x="50%" y="58%" textAnchor="middle" fill="#6b7280" fontSize="11">
          pass rate
        </text>
      </PieChart>
    </ResponsiveContainer>
  );
}

// ── Fix Cycles Bar Chart ────────────────────────────────────────────────────

function FixCyclesChart({ milestones }: { milestones: MilestoneTestAnalytics[] }) {
  const data = milestones
    .filter(m => m.bugfix_cycles > 0 || m.test_fix_cycles > 0 || m.test_runs > 0)
    .map(m => ({
      name: `M${m.id}`,
      bugfix: m.bugfix_cycles,
      testFix: m.test_fix_cycles,
      total: m.bugfix_cycles + m.test_fix_cycles,
    }));

  if (data.length === 0) {
    return (
      <div className="h-[240px] flex flex-col items-center justify-center text-text-muted">
        <CheckCircle2Icon className="w-8 h-8 mb-2 text-status-success/60" />
        <p className="text-sm">No fix cycles needed</p>
        <p className="text-xs mt-1">All milestones passed without fixes</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
        <XAxis dataKey="name" stroke="#6b7280" fontSize={12} />
        <YAxis stroke="#6b7280" fontSize={12} allowDecimals={false} />
        <Tooltip
          contentStyle={tooltipStyle}
          labelStyle={{ color: '#f9fafb', fontWeight: 600 }}
          cursor={{ fill: 'rgba(255,255,255,0.04)' }}
        />
        <Legend wrapperStyle={{ fontSize: '13px' }} />
        <Bar dataKey="bugfix" name="Bugfix Cycles" stackId="a" fill={STATUS_AMBER} radius={[0, 0, 0, 0]} />
        <Bar dataKey="testFix" name="Test Fix Cycles" stackId="a" fill={STATUS_RED} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── QA Report Timeline ──────────────────────────────────────────────────────

function QaReportTimeline({ reports, milestones }: { reports: TestAnalyticsData['qa_reports']; milestones: MilestoneTestAnalytics[] }) {
  const nameMap = new Map(milestones.map(m => [m.id, m.name]));

  return (
    <div className="overflow-auto max-h-[320px]">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-bg-secondary">
          <tr className="text-text-muted border-b border-border-subtle">
            <th className="text-left py-2 pr-3 font-medium">Milestone</th>
            <th className="text-center py-2 px-2 font-medium">Cycle</th>
            <th className="text-center py-2 px-2 font-medium">Result</th>
            <th className="text-right py-2 px-2 font-medium">Exit Code</th>
            <th className="text-left py-2 pl-2 font-medium">Report</th>
          </tr>
        </thead>
        <tbody>
          {reports.map((r, i) => (
            <tr key={i} className="border-b border-border-subtle/50 hover:bg-bg-tertiary/50 transition-colors">
              <td className="py-2 pr-3">
                <div className="flex items-center gap-2">
                  <span className="text-text-muted font-mono text-xs">M{r.milestone}</span>
                  <span className="text-text-primary">{nameMap.get(r.milestone) ?? `Milestone ${r.milestone}`}</span>
                </div>
              </td>
              <td className="text-center py-2 px-2">
                <span className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold ${
                  r.cycle === 0 ? 'bg-accent-cyan/20 text-accent-cyan' : 'bg-status-warning/20 text-status-warning'
                }`}>
                  {r.cycle}
                </span>
              </td>
              <td className="text-center py-2 px-2">
                <div className="flex items-center justify-center gap-1">
                  {r.passed ? (
                    <CheckCircle2Icon className="w-3.5 h-3.5 text-status-success" />
                  ) : (
                    <XCircleIcon className="w-3.5 h-3.5 text-status-error" />
                  )}
                  <StatusBadge variant={r.passed ? 'success' : 'error'}>
                    {r.passed ? 'Pass' : 'Fail'}
                  </StatusBadge>
                </div>
              </td>
              <td className="text-right py-2 px-2 font-mono text-text-secondary">
                {r.exit_code}
              </td>
              <td className="py-2 pl-2 text-text-muted font-mono text-xs truncate max-w-[200px]" title={r.file}>
                {r.file}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
