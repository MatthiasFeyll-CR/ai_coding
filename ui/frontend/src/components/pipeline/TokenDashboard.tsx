import { pipelineApi } from '@/api/client';
import type { TokenUsage } from '@/types';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  CoinsIcon,
  CpuIcon,
  DatabaseIcon,
  LayersIcon,
  ZapIcon,
} from 'lucide-react';
import { useState } from 'react';
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

interface TokenDashboardProps {
  projectId?: number;
}

// ── Color palette (matches tailwind theme) ──────────────────────────────────

const CHART_COLORS = ['#06b6d4', '#a855f7', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#14b8a6'];

const PHASE_COLORS: Record<string, string> = {
  prd_generation: '#3b82f6',
  ralph: '#a855f7',
  qa_review: '#10b981',
  merge_verify: '#f59e0b',
  reconciliation: '#06b6d4',
  test_fix: '#ef4444',
  gate_fix: '#ec4899',
  unknown: '#6b7280',
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatCost(usd: number): string {
  if (usd === 0) return '$0.00';
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  if (usd < 1) return `$${usd.toFixed(3)}`;
  return `$${usd.toFixed(2)}`;
}

function formatTokens(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`;
  return count.toLocaleString();
}

function formatPhaseName(phase: string): string {
  const names: Record<string, string> = {
    prd_generation: 'PRD Gen',
    ralph: 'Ralph',
    qa_review: 'QA Review',
    merge_verify: 'Merge',
    reconciliation: 'Reconcile',
    test_fix: 'Test Fix',
    gate_fix: 'Gate Fix',
    unknown: 'Other',
  };
  return names[phase] || phase;
}

function shortenModel(model: string): string {
  return model
    .replace('claude-', '')
    .replace('-20241022', '')
    .replace('-20250514', '');
}

// ── KPI Card ────────────────────────────────────────────────────────────────

interface KpiCardProps {
  label: string;
  value: string;
  subtitle?: string;
  icon: React.ReactNode;
  accentClass: string;
  glowClass?: string;
}

function KpiCard({ label, value, subtitle, icon, accentClass, glowClass }: KpiCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`bg-bg-secondary rounded-xl border border-border-subtle p-5 relative overflow-hidden ${glowClass ? `hover:shadow-${glowClass}` : ''} transition-shadow`}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-text-muted text-xs font-medium uppercase tracking-wider">{label}</p>
          <p className={`text-2xl font-bold ${accentClass}`}>{value}</p>
          {subtitle && <p className="text-text-muted text-xs">{subtitle}</p>}
        </div>
        <div className={`p-2.5 rounded-lg bg-bg-tertiary ${accentClass}`}>
          {icon}
        </div>
      </div>
    </motion.div>
  );
}

// ── Chart Card Wrapper ──────────────────────────────────────────────────────

interface ChartCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

function ChartCard({ title, subtitle, children }: ChartCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-bg-secondary rounded-xl border border-border-subtle p-5"
    >
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
        {subtitle && <p className="text-xs text-text-muted mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </motion.div>
  );
}

// ── Custom Tooltip ──────────────────────────────────────────────────────────

const tooltipStyle = {
  backgroundColor: '#111827',
  border: '1px solid #374151',
  borderRadius: '8px',
  fontSize: '12px',
  boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
};

// ── Main Component ──────────────────────────────────────────────────────────

export function TokenDashboard({ projectId }: TokenDashboardProps) {
  const [historyView, setHistoryView] = useState<'table' | 'chart'>('table');

  const { data: tokenData, isLoading } = useQuery({
    queryKey: ['tokens', projectId],
    queryFn: () => pipelineApi.getTokens(projectId!).then((res) => res.data),
    enabled: !!projectId,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-text-muted">
          <div className="w-5 h-5 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
          Loading cost data...
        </div>
      </div>
    );
  }

  if (!tokenData || tokenData.total.invocations === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center">
        <CoinsIcon className="w-12 h-12 text-text-muted mb-3" />
        <h3 className="text-lg font-semibold text-text-primary mb-1">No Cost Data Yet</h3>
        <p className="text-text-muted text-sm max-w-md">
          Cost tracking data will appear here once the pipeline starts running AI invocations.
        </p>
      </div>
    );
  }

  const { total, by_milestone, by_phase, by_model, history } = tokenData;

  // ── Derived chart data ──────────────────────────────────────────────────

  const totalTokens = total.input_tokens + total.output_tokens;
  const cacheHitRate = totalTokens > 0
    ? ((total.cache_read_tokens / (total.input_tokens + total.cache_read_tokens)) * 100)
    : 0;

  // Cost by model (horizontal bar)
  const modelData = Object.entries(by_model)
    .map(([model, data]) => ({
      name: shortenModel(model),
      cost: data.cost_usd,
      invocations: data.invocations,
      tokens: data.input_tokens + data.output_tokens,
    }))
    .sort((a, b) => b.cost - a.cost);

  // Cost by phase (vertical bar)
  const phaseData = Object.entries(by_phase)
    .map(([phase, data]) => ({
      name: formatPhaseName(phase),
      phase,
      cost: data.cost_usd,
      input: data.input_tokens,
      output: data.output_tokens,
      invocations: data.invocations,
    }))
    .sort((a, b) => b.cost - a.cost);

  // Tokens by milestone (stacked bar)
  const milestoneBarData = Object.entries(by_milestone)
    .map(([id, data]) => ({
      name: `M${id}`,
      input: data.input_tokens,
      output: data.output_tokens,
      cached: data.cache_read_tokens,
      cost: data.cost_usd,
    }))
    .sort((a, b) => Number(a.name.slice(1)) - Number(b.name.slice(1)));

  // Cost distribution donut (by milestone)
  const milestonePieData = Object.entries(by_milestone)
    .map(([id, data]) => ({
      name: `M${id}`,
      value: data.cost_usd,
    }))
    .filter((d) => d.value > 0);

  // History timeline (most recent first)
  const sortedHistory = [...history].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="space-y-6">
      {/* ── KPI Cards ────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Total Cost"
          value={formatCost(total.cost_usd)}
          subtitle={`${total.invocations} invocations`}
          icon={<CoinsIcon className="w-5 h-5" />}
          accentClass="text-status-success"
          glowClass="glow-green"
        />
        <KpiCard
          label="Total Tokens"
          value={formatTokens(totalTokens)}
          subtitle={`${formatTokens(total.input_tokens)} in · ${formatTokens(total.output_tokens)} out`}
          icon={<CpuIcon className="w-5 h-5" />}
          accentClass="text-accent-cyan"
          glowClass="glow-cyan"
        />
        <KpiCard
          label="Cache Savings"
          value={`${cacheHitRate.toFixed(1)}%`}
          subtitle={`${formatTokens(total.cache_read_tokens)} tokens cached`}
          icon={<DatabaseIcon className="w-5 h-5" />}
          accentClass="text-accent-purple"
          glowClass="glow-purple"
        />
        <KpiCard
          label="Models Used"
          value={String(Object.keys(by_model).length)}
          subtitle={Object.keys(by_model).map(shortenModel).join(', ')}
          icon={<LayersIcon className="w-5 h-5" />}
          accentClass="text-accent-blue"
          glowClass="glow-blue"
        />
      </div>

      {/* ── Row 1: Cost by Model + Cost by Phase ─────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cost by Model — Horizontal Bar */}
        <ChartCard title="Cost by Model" subtitle="Which models cost the most">
          <ResponsiveContainer width="100%" height={Math.max(200, modelData.length * 48)}>
            <BarChart data={modelData} layout="vertical" margin={{ left: 20, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
              <XAxis type="number" stroke="#6b7280" fontSize={11} tickFormatter={(v) => formatCost(v)} />
              <YAxis type="category" dataKey="name" stroke="#6b7280" fontSize={11} width={100} />
              <Tooltip
                contentStyle={tooltipStyle}
                formatter={(value: number, name: string) => {
                  if (name === 'cost') return [formatCost(value), 'Cost'];
                  return [value, name];
                }}
                labelStyle={{ color: '#f9fafb', fontWeight: 600 }}
              />
              <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
                {modelData.map((_, index) => (
                  <Cell key={`model-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Cost by Phase — Vertical Bar */}
        <ChartCard title="Cost by Phase" subtitle="Pipeline phase cost breakdown">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={phaseData} margin={{ bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="name" stroke="#6b7280" fontSize={11} />
              <YAxis stroke="#6b7280" fontSize={11} tickFormatter={(v) => formatCost(v)} />
              <Tooltip
                contentStyle={tooltipStyle}
                formatter={(value: number, name: string) => {
                  if (name === 'Cost') return [formatCost(value), 'Cost'];
                  return [formatTokens(value), name];
                }}
                labelStyle={{ color: '#f9fafb', fontWeight: 600 }}
              />
              <Bar dataKey="cost" name="Cost" radius={[4, 4, 0, 0]}>
                {phaseData.map((entry) => (
                  <Cell key={entry.phase} fill={PHASE_COLORS[entry.phase] || '#6b7280'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* ── Row 2: Tokens by Milestone + Cost Distribution ───────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Tokens by Milestone — Stacked Bar (span 2 cols) */}
        <ChartCard title="Tokens by Milestone" subtitle="Input, output, and cached token breakdown">
          <div className="lg:col-span-2">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={milestoneBarData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="name" stroke="#6b7280" fontSize={11} />
                <YAxis stroke="#6b7280" fontSize={11} tickFormatter={(v) => formatTokens(v)} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value: number, name: string) => [formatTokens(value), name]}
                  labelStyle={{ color: '#f9fafb', fontWeight: 600 }}
                />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
                <Bar dataKey="input" stackId="a" fill="#06b6d4" name="Input" />
                <Bar dataKey="output" stackId="a" fill="#a855f7" name="Output" />
                <Bar dataKey="cached" stackId="a" fill="#374151" name="Cached" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        {/* Cost Distribution — Donut */}
        <ChartCard title="Cost by Milestone" subtitle="Proportional cost distribution">
          {milestonePieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={milestonePieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                  strokeWidth={0}
                >
                  {milestonePieData.map((_, index) => (
                    <Cell key={`pie-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value: number) => [formatCost(value), 'Cost']}
                />
                <Legend
                  wrapperStyle={{ fontSize: '11px' }}
                  formatter={(value) => <span className="text-text-secondary">{value}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[280px] flex items-center justify-center text-text-muted text-sm">
              No milestone cost data
            </div>
          )}
        </ChartCard>

        {/* Phase detail mini-table filling the remaining col */}
        <ChartCard title="Phase Details" subtitle="Tokens and invocations per phase">
          <div className="overflow-auto max-h-[280px]">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted border-b border-border-subtle">
                  <th className="text-left py-2 pr-3 font-medium">Phase</th>
                  <th className="text-right py-2 px-2 font-medium">In</th>
                  <th className="text-right py-2 px-2 font-medium">Out</th>
                  <th className="text-right py-2 pl-2 font-medium">Cost</th>
                </tr>
              </thead>
              <tbody>
                {phaseData.map((row) => (
                  <tr key={row.phase} className="border-b border-border-subtle/50 hover:bg-bg-tertiary/50">
                    <td className="py-2 pr-3">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{ backgroundColor: PHASE_COLORS[row.phase] || '#6b7280' }}
                        />
                        <span className="text-text-primary">{row.name}</span>
                      </div>
                    </td>
                    <td className="text-right py-2 px-2 text-text-secondary font-mono">
                      {formatTokens(row.input)}
                    </td>
                    <td className="text-right py-2 px-2 text-text-secondary font-mono">
                      {formatTokens(row.output)}
                    </td>
                    <td className="text-right py-2 pl-2 text-status-success font-mono">
                      {formatCost(row.cost)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartCard>
      </div>

      {/* ── Invocation History ────────────────────────────────────────────── */}
      <ChartCard
        title="Invocation History"
        subtitle={`${sortedHistory.length} API calls recorded`}
      >
        {/* View toggle */}
        <div className="flex gap-1 mb-4 p-0.5 bg-bg-tertiary rounded-lg w-fit">
          <button
            onClick={() => setHistoryView('table')}
            className={`px-3 py-1 text-xs rounded-md transition-colors ${
              historyView === 'table'
                ? 'bg-bg-secondary text-text-primary shadow-sm'
                : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            Table
          </button>
          <button
            onClick={() => setHistoryView('chart')}
            className={`px-3 py-1 text-xs rounded-md transition-colors ${
              historyView === 'chart'
                ? 'bg-bg-secondary text-text-primary shadow-sm'
                : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            Timeline
          </button>
        </div>

        {historyView === 'chart' ? (
          <HistoryChart history={sortedHistory} />
        ) : (
          <HistoryTable history={sortedHistory} />
        )}
      </ChartCard>
    </div>
  );
}

// ── History Timeline Chart ──────────────────────────────────────────────────

function HistoryChart({ history }: { history: TokenUsage['history'] }) {
  const data = [...history]
    .reverse()
    .map((h, i) => ({
      idx: i + 1,
      cost: h.cost_usd,
      model: shortenModel(h.model),
      phase: formatPhaseName(h.phase || 'unknown'),
      phaseKey: h.phase || 'unknown',
    }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
        <XAxis dataKey="idx" stroke="#6b7280" fontSize={10} label={{ value: 'Invocation #', position: 'insideBottom', offset: -2, fill: '#6b7280', fontSize: 10 }} />
        <YAxis stroke="#6b7280" fontSize={10} tickFormatter={(v) => formatCost(v)} />
        <Tooltip
          contentStyle={tooltipStyle}
          labelFormatter={(label) => `Invocation #${label}`}
          formatter={(value: number, _: string, props: any) => [
            formatCost(value),
            `${props.payload.phase} (${props.payload.model})`,
          ]}
        />
        <Bar dataKey="cost" radius={[2, 2, 0, 0]}>
          {data.map((entry, index) => (
            <Cell key={index} fill={PHASE_COLORS[entry.phaseKey] || '#6b7280'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── History Table ───────────────────────────────────────────────────────────

function HistoryTable({ history }: { history: TokenUsage['history'] }) {
  return (
    <div className="overflow-auto max-h-[320px]">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-bg-secondary">
          <tr className="text-text-muted border-b border-border-subtle">
            <th className="text-left py-2 pr-3 font-medium">Time</th>
            <th className="text-left py-2 px-2 font-medium">Phase</th>
            <th className="text-left py-2 px-2 font-medium">Model</th>
            <th className="text-right py-2 px-2 font-medium">In</th>
            <th className="text-right py-2 px-2 font-medium">Out</th>
            <th className="text-right py-2 px-2 font-medium">Cached</th>
            <th className="text-right py-2 pl-2 font-medium">Cost</th>
          </tr>
        </thead>
        <tbody>
          {history.map((row) => (
            <tr
              key={row.id}
              className="border-b border-border-subtle/50 hover:bg-bg-tertiary/50 transition-colors"
            >
              <td className="py-2 pr-3 text-text-muted whitespace-nowrap">
                {new Date(row.created_at).toLocaleTimeString()}
              </td>
              <td className="py-2 px-2">
                <div className="flex items-center gap-1.5">
                  <div
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: PHASE_COLORS[row.phase || 'unknown'] || '#6b7280' }}
                  />
                  <span className="text-text-primary">{formatPhaseName(row.phase || 'unknown')}</span>
                </div>
              </td>
              <td className="py-2 px-2 text-text-secondary font-mono">
                {shortenModel(row.model)}
              </td>
              <td className="text-right py-2 px-2 text-accent-cyan font-mono">
                {formatTokens(row.input_tokens)}
              </td>
              <td className="text-right py-2 px-2 text-accent-purple font-mono">
                {formatTokens(row.output_tokens)}
              </td>
              <td className="text-right py-2 px-2 text-text-muted font-mono">
                {formatTokens(row.cache_read_tokens)}
              </td>
              <td className="text-right py-2 pl-2 text-status-success font-mono font-medium">
                {formatCost(row.cost_usd)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {history.length === 0 && (
        <div className="py-8 text-center text-text-muted text-sm">
          No invocations recorded yet
        </div>
      )}
    </div>
  );
}
