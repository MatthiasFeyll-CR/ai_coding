import { pipelineApi } from '@/api/client';
import type { TokenUsage } from '@/types';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
    AlertTriangleIcon,
    CoinsIcon,
    CpuIcon,
    DatabaseIcon,
    LayersIcon
} from 'lucide-react';
import { useState } from 'react';
import {
    Area,
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    ComposedChart,
    Legend,
    Line,
    Pie,
    PieChart,
    ReferenceLine,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis
} from 'recharts';

interface TokenDashboardProps {
  projectId?: number;
}

// ── Color palette (matches tailwind theme) ──────────────────────────────────

const CHART_COLORS = ['#06b6d4', '#a855f7', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#14b8a6'];

const PHASE_COLORS: Record<string, string> = {
  phase0_scaffolding: '#14b8a6',
  phase0_test_infra: '#0ea5e9',
  phase0_lifecycle: '#8b5cf6',
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
    phase0_scaffolding: 'Scaffolding',
    phase0_test_infra: 'Test Infra',
    phase0_lifecycle: 'Lifecycle',
    prd_generation: 'PRD Gen',
    ralph: 'Ralph',
    qa_review: 'QA Review',
    merge_verify: 'Merge',
    reconciliation: 'Reconcile',
    test_fix: 'Test Fix',
    gate_fix: 'Gate Fix',
    unknown: 'Other',
  };
  return names[phase] || phase.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
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
        <h3 className="text-base font-semibold text-text-primary">{title}</h3>
        {subtitle && <p className="text-sm text-text-muted mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </motion.div>
  );
}

// ── Custom Tooltip ──────────────────────────────────────────────────────────

const tooltipStyle: React.CSSProperties = {
  backgroundColor: '#1f2937',
  border: '1px solid #4b5563',
  borderRadius: '8px',
  fontSize: '13px',
  boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
  color: '#f9fafb',
};

const tooltipLabelStyle: React.CSSProperties = {
  color: '#f9fafb',
  fontWeight: 600,
};

const tooltipItemStyle: React.CSSProperties = {
  color: '#e5e7eb',
};

// ── Main Component ──────────────────────────────────────────────────────────

export function TokenDashboard({ projectId }: TokenDashboardProps) {
  const [historyView, setHistoryView] = useState<'table' | 'chart'>('table');

  const { data: tokenData, isLoading } = useQuery({
    queryKey: ['tokens', projectId],
    queryFn: () => pipelineApi.getTokens(projectId!).then((res) => res.data),
    enabled: !!projectId,
    refetchInterval: 5000,
  });

  // Fetch overview for budget + milestone counts (used for forecast)
  const { data: overviewData } = useQuery({
    queryKey: ['overview', projectId],
    queryFn: () => pipelineApi.getOverview(projectId!).then((res) => res.data),
    enabled: !!projectId,
    refetchInterval: 5000,
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
      <div className="relative">
        {/* Placeholder skeleton layout */}
        <div className="space-y-6 pointer-events-none select-none">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {['Total Cost', 'Total Tokens', 'Cache Savings', 'Models Used'].map((label) => (
              <div key={label} className="bg-bg-secondary rounded-xl border border-border-subtle p-5">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-9 h-9 rounded-lg bg-bg-tertiary" />
                  <span className="text-xs text-text-muted uppercase tracking-wider">{label}</span>
                </div>
                <div className="h-8 w-20 bg-bg-tertiary rounded" />
                <div className="h-3 w-32 bg-bg-tertiary rounded mt-2" />
              </div>
            ))}
          </div>
          <div className="bg-bg-secondary rounded-xl border border-border-subtle p-5">
            <div className="h-4 w-32 bg-bg-tertiary rounded mb-4" />
            <div className="h-[220px] bg-bg-tertiary/50 rounded" />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-bg-secondary rounded-xl border border-border-subtle p-5">
              <div className="h-4 w-28 bg-bg-tertiary rounded mb-4" />
              <div className="h-[200px] bg-bg-tertiary/50 rounded" />
            </div>
            <div className="bg-bg-secondary rounded-xl border border-border-subtle p-5">
              <div className="h-4 w-28 bg-bg-tertiary rounded mb-4" />
              <div className="h-[200px] bg-bg-tertiary/50 rounded" />
            </div>
          </div>
        </div>
        {/* Overlay */}
        <div className="absolute inset-0 flex items-center justify-center z-10">
          <div className="bg-bg-secondary/70 backdrop-blur-sm border border-border-subtle rounded-2xl px-10 py-8 flex flex-col items-center text-center shadow-xl max-w-md">
            <CoinsIcon className="w-10 h-10 text-text-muted mb-3 opacity-60" />
            <h3 className="text-base font-semibold text-text-primary mb-1">No Cost Data Yet</h3>
            <p className="text-text-muted text-sm leading-relaxed">
              Cost tracking data will appear here once the pipeline starts running AI invocations.
            </p>
          </div>
        </div>
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
      key: phase,
      phase: formatPhaseName(phase),
      cost: data.cost_usd,
      input: data.input_tokens,
      output: data.output_tokens,
      cached: data.cache_read_tokens ?? 0,
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

  // History timeline (most recent first; fall back to array order when timestamps missing)
  const sortedHistory = [...history].sort((a, b) => {
    if (a.created_at && b.created_at) {
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    }
    return (b.id ?? 0) - (a.id ?? 0);
  });

  // Cumulative cost over time (chronological order)
  const cumulativeCostData = (() => {
    const chronological = [...history].sort((a, b) => {
      if (a.created_at && b.created_at) {
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      return (a.id ?? 0) - (b.id ?? 0);
    });
    let running = 0;
    return chronological.map((h, i) => {
      running += h.cost_usd;
      return {
        idx: i + 1,
        cumulative: running,
        cost: h.cost_usd,
        phase: formatPhaseName(h.phase || 'unknown'),
        time: h.created_at ? new Date(h.created_at).toLocaleTimeString() : `#${i + 1}`,
      };
    });
  })();

  // ── Cost Forecast Computation ─────────────────────────────────────────
  // Uses per-phase token consumption from completed milestones, weighted
  // by story count (effort proxy), and projected using the pricing model
  // of each phase to estimate costs for remaining milestones.
  const forecastData = (() => {
    const completedMilestones = overviewData?.progress.completed_milestones ?? 0;
    const totalMilestones = overviewData?.progress.total_milestones ?? 0;
    const remainingMilestones = totalMilestones - completedMilestones;
    const budgetUsd = overviewData?.cost.budget_usd ?? 0;
    const milestoneDetails = overviewData?.milestone_details ?? [];

    // Need at least 1 completed milestone to forecast
    if (completedMilestones < 1 || remainingMilestones <= 0 || cumulativeCostData.length === 0) {
      return { points: [] as typeof cumulativeCostData, forecastTotal: 0, budgetUsd, method: 'none' as const };
    }

    // Gather completed and remaining milestones (excluding Phase 0 id=0)
    const completedMs = milestoneDetails.filter(m => m.completed && m.id !== 0);
    const remainingMs = milestoneDetails.filter(m => !m.completed && m.id !== 0);

    // Total stories in completed milestones (for per-story rate)
    const completedStories = completedMs.reduce((s, m) => s + (m.stories || 1), 0);
    const remainingStories = remainingMs.reduce((s, m) => s + (m.stories || 1), 0);

    // Phase 0 is a one-time cost - isolate it
    const phase0Cost = by_milestone['0']?.cost_usd ?? 0;
    const milestoneCosts = total.cost_usd - phase0Cost;

    // --- Per-phase cost-per-story approach ---
    // Get actual per-phase costs (excluding phase0 phases)
    const phase0Phases = ['phase0_scaffolding', 'phase0_test_infra', 'phase0_lifecycle'];
    const milestonePhases = Object.entries(by_phase)
      .filter(([key]) => !phase0Phases.includes(key));

    let forecastRemaining: number;
    let method: 'per_story' | 'median' | 'average';

    if (completedStories > 0 && milestonePhases.length > 0) {
      // Method 1: Per-phase cost-per-story rate × remaining stories
      // Each phase has a cost rate per story from completed milestones
      const costPerStoryByPhase = milestonePhases.map(([phaseName, data]) => ({
        phase: phaseName,
        costPerStory: data.cost_usd / completedStories,
        totalCost: data.cost_usd,
      }));

      // Total cost per story across all phases
      const totalCostPerStory = costPerStoryByPhase.reduce((s, p) => s + p.costPerStory, 0);

      // Project remaining cost based on remaining stories
      forecastRemaining = totalCostPerStory * remainingStories;
      method = 'per_story';
    } else {
      // Fallback: use median of per-milestone costs
      const mCosts = Object.entries(by_milestone)
        .filter(([k]) => k !== '0')
        .map(([, data]) => data.cost_usd)
        .sort((a, b) => a - b);

      let avgCostPerMs: number;
      if (mCosts.length >= 2) {
        const mid = Math.floor(mCosts.length / 2);
        avgCostPerMs = mCosts.length % 2 === 0
          ? (mCosts[mid - 1] + mCosts[mid]) / 2
          : mCosts[mid];
        method = 'median';
      } else {
        avgCostPerMs = mCosts.length > 0 ? mCosts[0] : milestoneCosts / Math.max(1, completedMs.length);
        method = 'average';
      }
      forecastRemaining = avgCostPerMs * remainingMs.length;
    }

    const forecastTotal = total.cost_usd + forecastRemaining;

    // Estimate invocations per milestone from history (excluding phase0)
    const nonPhase0History = history.filter(h => h.milestone_id !== 0);
    const actualComplete = completedMs.length || 1;
    const avgInvocationsPerMilestone = Math.max(
      Math.round(nonPhase0History.length / actualComplete), 3
    );

    // Generate forecast points
    const lastIdx = cumulativeCostData.length;
    const lastCumulative = cumulativeCostData[cumulativeCostData.length - 1].cumulative;
    const forecastPoints: Array<{ idx: number; cumulative?: number; forecast: number; cost: number; phase: string; time: string }> = [];

    // Bridge point
    forecastPoints.push({
      idx: lastIdx,
      cumulative: lastCumulative,
      forecast: lastCumulative,
      cost: 0,
      phase: 'Forecast',
      time: 'Forecast start',
    });

    // Distribute remaining cost by each remaining milestone's story weight
    const totalRemainingStories = remainingMs.reduce((s, m) => s + (m.stories || 1), 0);
    let runningForecast = lastCumulative;

    for (let i = 0; i < remainingMs.length; i++) {
      const m = remainingMs[i];
      const storyWeight = totalRemainingStories > 0
        ? (m.stories || 1) / totalRemainingStories
        : 1 / remainingMs.length;
      const mCost = forecastRemaining * storyWeight;
      runningForecast += mCost;

      forecastPoints.push({
        idx: lastIdx + avgInvocationsPerMilestone * (i + 1),
        forecast: runningForecast,
        cost: mCost,
        phase: 'Forecast',
        time: `Projected M${m.id} (${m.stories || '?'} stories)`,
      });
    }

    return { points: forecastPoints, forecastTotal, budgetUsd, method };
  })();

  // Merge actual + forecast data for the combined chart
  const combinedCostData = (() => {
    const actual = cumulativeCostData.map((d) => ({
      ...d,
      forecast: undefined as number | undefined,
    }));

    if (forecastData.points.length > 0) {
      // Replace the bridge point (first forecast point has same idx as last actual)
      const forecastPoints = forecastData.points.slice(1).map((d) => ({
        ...d,
        cumulative: undefined as number | undefined,
      }));
      // Add forecast value to the last actual point (bridge)
      if (actual.length > 0) {
        actual[actual.length - 1].forecast = actual[actual.length - 1].cumulative;
      }
      return [...actual, ...forecastPoints];
    }
    return actual;
  })();

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

      {/* ── Cumulative Cost Line Chart with Forecast ────────────────────── */}
      {cumulativeCostData.length > 1 && (
        <ChartCard title="Cumulative Cost" subtitle="Running total spend over invocations">
          <div className="flex gap-4">
            {/* Chart */}
            <div className="flex-1 min-w-0">
              <ResponsiveContainer width="100%" height={260}>
                <ComposedChart data={combinedCostData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                  <defs>
                    <linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="forecastGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#a855f7" stopOpacity={0.1} />
                      <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis
                    dataKey="idx"
                    stroke="#6b7280"
                    fontSize={12}
                    label={{ value: 'Invocation #', position: 'insideBottom', offset: -2, fill: '#6b7280', fontSize: 12 }}
                  />
                  <YAxis
                    stroke="#6b7280"
                    fontSize={12}
                    tickFormatter={(v) => formatCost(v)}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    labelStyle={tooltipLabelStyle}
                    itemStyle={tooltipItemStyle}
                    labelFormatter={(label) => `Invocation #${label}`}
                    formatter={(value: number, name: string) => {
                      if (value === undefined || value === null) return [null, null];
                      if (name === 'forecast') return [formatCost(value), 'Forecast'];
                      return [formatCost(value), name === 'cumulative' ? 'Running Total' : 'This Call'];
                    }}
                  />
                  {/* Budget reference line */}
                  {forecastData.budgetUsd > 0 && (
                    <ReferenceLine
                      y={forecastData.budgetUsd}
                      stroke="#f59e0b"
                      strokeDasharray="8 4"
                      strokeWidth={1.5}
                      label={{
                        value: `Budget ${formatCost(forecastData.budgetUsd)}`,
                        position: 'right',
                        fill: '#f59e0b',
                        fontSize: 12,
                      }}
                    />
                  )}
                  <Area
                    type="monotone"
                    dataKey="cumulative"
                    stroke="#06b6d4"
                    strokeWidth={2}
                    fill="url(#costGradient)"
                    dot={false}
                    activeDot={{ r: 4, fill: '#06b6d4', stroke: '#111827', strokeWidth: 2 }}
                    connectNulls={false}
                  />
                  {forecastData.points.length > 0 && (
                    <Line
                      type="monotone"
                      dataKey="forecast"
                      stroke="#a855f7"
                      strokeWidth={2}
                      strokeDasharray="6 4"
                      dot={{ r: 3, fill: '#a855f7', stroke: '#111827', strokeWidth: 2 }}
                      activeDot={{ r: 5, fill: '#a855f7', stroke: '#111827', strokeWidth: 2 }}
                      connectNulls={true}
                    />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* Forecast budget indicator (right side) */}
            {forecastData.points.length > 0 && (
              <div className="flex flex-col items-center justify-center w-28 shrink-0 gap-3 border-l border-border-subtle pl-4">
                <div className="text-center">
                  <p className="text-xs text-text-muted uppercase tracking-wider mb-1">Forecast</p>
                  <p className="text-lg font-bold text-accent-purple">{formatCost(forecastData.forecastTotal)}</p>
                </div>
                {forecastData.budgetUsd > 0 && (
                  <div className="text-center">
                    <p className="text-xs text-text-muted uppercase tracking-wider mb-1">Budget</p>
                    <p className={`text-lg font-bold ${forecastData.forecastTotal > forecastData.budgetUsd ? 'text-status-error' : 'text-status-success'}`}>
                      {formatCost(forecastData.budgetUsd)}
                    </p>
                    {forecastData.forecastTotal > forecastData.budgetUsd && (
                      <p className="text-xs text-status-error mt-1">
                        +{formatCost(forecastData.forecastTotal - forecastData.budgetUsd)} over
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Forecast disclaimer */}
          {forecastData.points.length > 0 && (
            <div className="flex items-start gap-2 mt-3 pt-3 border-t border-border-subtle">
              <AlertTriangleIcon className="w-3.5 h-3.5 text-status-warning shrink-0 mt-0.5" />
              <p className="text-xs text-text-muted leading-relaxed">
                {forecastData.method === 'per_story'
                  ? 'Forecast uses per-phase cost rates from completed milestones, weighted by user story count for each remaining milestone.'
                  : forecastData.method === 'median'
                  ? 'Forecast uses the median cost of completed milestones. More data will improve accuracy.'
                  : 'Forecast is a rough estimate based on the average cost of completed milestones. Actual costs may differ significantly.'
                }
              </p>
            </div>
          )}
        </ChartCard>
      )}

      {/* ── Row 1: Cost by Model + Cost by Phase ─────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cost by Model — Horizontal Bar */}
        <ChartCard title="Cost by Model" subtitle="Which models cost the most">
          <ResponsiveContainer width="100%" height={Math.max(200, modelData.length * 48)}>
            <BarChart data={modelData} layout="vertical" margin={{ left: 20, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
              <XAxis type="number" stroke="#6b7280" fontSize={12} tickFormatter={(v) => formatCost(v)} />
              <YAxis type="category" dataKey="name" stroke="#6b7280" fontSize={12} width={100} />
              <Tooltip
                contentStyle={tooltipStyle}
                labelStyle={tooltipLabelStyle}
                itemStyle={tooltipItemStyle}
                cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                formatter={(value: number, name: string) => {
                  if (name === 'cost') return [formatCost(value), 'Cost'];
                  return [value, name];
                }}
              />
              <Bar dataKey="cost" radius={[0, 4, 4, 0]} label={{ position: 'right', fill: '#9ca3af', fontSize: 12, formatter: (v: number) => formatCost(v) }}>
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
              <XAxis dataKey="name" stroke="#6b7280" fontSize={12} />
              <YAxis stroke="#6b7280" fontSize={12} tickFormatter={(v) => formatCost(v)} />
              <Tooltip
                contentStyle={tooltipStyle}
                labelStyle={tooltipLabelStyle}
                itemStyle={tooltipItemStyle}
                cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                formatter={(value: number, name: string) => {
                  if (name === 'Cost') return [formatCost(value), 'Cost'];
                  return [formatTokens(value), name];
                }}
              />
              <Bar dataKey="cost" name="Cost" radius={[4, 4, 0, 0]} label={{ position: 'top', fill: '#9ca3af', fontSize: 12, formatter: (v: number) => formatCost(v) }}>
                {phaseData.map((entry) => (
                  <Cell key={entry.key} fill={PHASE_COLORS[entry.key] || '#6b7280'} />
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
                <XAxis dataKey="name" stroke="#6b7280" fontSize={12} />
                <YAxis stroke="#6b7280" fontSize={12} tickFormatter={(v) => formatTokens(v)} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelStyle={tooltipLabelStyle}
                  itemStyle={tooltipItemStyle}
                  cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                  formatter={(value: number, name: string) => [formatTokens(value), name]}
                />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
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
                  labelStyle={tooltipLabelStyle}
                  itemStyle={tooltipItemStyle}
                  formatter={(value: number) => [formatCost(value), 'Cost']}
                />
                <Legend
                  wrapperStyle={{ fontSize: '12px' }}
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
            <table className="w-full text-sm">
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
                  <tr key={row.key} className="border-b border-border-subtle/50 hover:bg-bg-tertiary/50">
                    <td className="py-2 pr-3">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{ backgroundColor: PHASE_COLORS[row.key] || '#6b7280' }}
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

      {/* ── Cache Savings Per Phase ──────────────────────────────────────── */}
      {phaseData.length > 0 && (
        <ChartCard title="Cache Savings by Phase" subtitle="Cache read tokens saved per pipeline phase">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Bar chart */}
            <ResponsiveContainer width="100%" height={260}>
              <BarChart
                data={phaseData.map(p => {
                  const totalIn = p.input + p.cached;
                  const pct = totalIn > 0 ? (p.cached / totalIn) * 100 : 0;
                  // Estimate cost savings: cached tokens priced at ~$3/MTok input rate
                  const savedUsd = (p.cached / 1_000_000) * 3.0;
                  return { name: p.phase, cachePercent: pct, cachedTokens: p.cached, savedUsd };
                })}
                layout="vertical"
                margin={{ top: 5, right: 30, bottom: 5, left: 10 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} stroke="#6b7280" fontSize={12} />
                <YAxis type="category" dataKey="name" width={100} stroke="#6b7280" fontSize={12} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelStyle={tooltipLabelStyle}
                  itemStyle={tooltipItemStyle}
                  cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                  formatter={(value: number, name: string, props: { payload: { cachedTokens: number; savedUsd: number } }) => {
                    if (name === 'cachePercent') {
                      return [`${value.toFixed(1)}% (${formatTokens(props.payload.cachedTokens)} tokens, ~${formatCost(props.payload.savedUsd)} saved)`, 'Cache Hit'];
                    }
                    return [value, name];
                  }}
                />
                <Bar dataKey="cachePercent" name="cachePercent" radius={[0, 4, 4, 0]} label={{ position: 'right', fill: '#9ca3af', fontSize: 12, formatter: (v: number) => `${v.toFixed(0)}%` }}>
                  {phaseData.map((_, index) => {
                    const totalIn = phaseData[index].input + phaseData[index].cached;
                    const pct = totalIn > 0 ? (phaseData[index].cached / totalIn) * 100 : 0;
                    return (
                      <Cell
                        key={`cache-${index}`}
                        fill={pct >= 80 ? '#10b981' : pct >= 50 ? '#06b6d4' : '#6b7280'}
                      />
                    );
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>

            {/* Summary table */}
            <div className="overflow-auto max-h-[260px]">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-bg-secondary">
                  <tr className="text-text-muted border-b border-border-subtle">
                    <th className="text-left py-2 pr-3 font-medium">Phase</th>
                    <th className="text-right py-2 px-2 font-medium">Input</th>
                    <th className="text-right py-2 px-2 font-medium">Cached</th>
                    <th className="text-right py-2 px-2 font-medium">Cache %</th>
                    <th className="text-right py-2 pl-2 font-medium">~Saved</th>
                  </tr>
                </thead>
                <tbody>
                  {phaseData.map((row) => {
                    const totalIn = row.input + row.cached;
                    const pct = totalIn > 0 ? (row.cached / totalIn) * 100 : 0;
                    const savedUsd = (row.cached / 1_000_000) * 3.0;
                    return (
                      <tr key={row.phase} className="border-b border-border-subtle/50 hover:bg-bg-tertiary/50 transition-colors">
                        <td className="py-2 pr-3">
                          <div className="flex items-center gap-1.5">
                            <div className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                              style={{ backgroundColor: PHASE_COLORS[row.key] || '#6b7280' }} />
                            <span className="text-text-primary">{row.phase}</span>
                          </div>
                        </td>
                        <td className="text-right py-2 px-2 text-accent-cyan font-mono">{formatTokens(row.input)}</td>
                        <td className="text-right py-2 px-2 text-text-muted font-mono">{formatTokens(row.cached)}</td>
                        <td className="text-right py-2 px-2 font-mono">
                          <span className={pct >= 80 ? 'text-status-success' : pct >= 50 ? 'text-accent-cyan' : 'text-text-muted'}>
                            {pct.toFixed(1)}%
                          </span>
                        </td>
                        <td className="text-right py-2 pl-2 text-status-success font-mono">{formatCost(savedUsd)}</td>
                      </tr>
                    );
                  })}
                  {/* Total row */}
                  <tr className="border-t border-border-subtle font-medium">
                    <td className="py-2 pr-3 text-text-primary">Total</td>
                    <td className="text-right py-2 px-2 text-accent-cyan font-mono">{formatTokens(phaseData.reduce((s, r) => s + r.input, 0))}</td>
                    <td className="text-right py-2 px-2 text-text-muted font-mono">{formatTokens(phaseData.reduce((s, r) => s + r.cached, 0))}</td>
                    <td className="text-right py-2 px-2 text-accent-purple font-mono">{cacheHitRate.toFixed(1)}%</td>
                    <td className="text-right py-2 pl-2 text-status-success font-mono">{formatCost((phaseData.reduce((s, r) => s + r.cached, 0) / 1_000_000) * 3.0)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </ChartCard>
      )}

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
        <XAxis dataKey="idx" stroke="#6b7280" fontSize={12} label={{ value: 'Invocation #', position: 'insideBottom', offset: -2, fill: '#6b7280', fontSize: 12 }} />
        <YAxis stroke="#6b7280" fontSize={12} tickFormatter={(v) => formatCost(v)} />
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

// ── Sortable Table Header ────────────────────────────────────────────────────

type SortDir = 'asc' | 'desc';

function SortHeader({
  label,
  sortKey,
  currentKey,
  currentDir,
  onSort,
  align = 'left',
  className = '',
}: {
  label: string;
  sortKey: string;
  currentKey: string;
  currentDir: SortDir;
  onSort: (key: string) => void;
  align?: 'left' | 'right' | 'center';
  className?: string;
}) {
  const active = currentKey === sortKey;
  const textAlign = align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left';
  return (
    <th
      className={`py-2 font-medium cursor-pointer select-none hover:text-text-primary transition-colors ${textAlign} ${className}`}
      onClick={() => onSort(sortKey)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <span className={`text-xs ${active ? 'text-accent-cyan' : 'text-text-muted/40'}`}>
          {active ? (currentDir === 'asc' ? '▲' : '▼') : '⇅'}
        </span>
      </span>
    </th>
  );
}

function useSortable<T>(data: T[], defaultKey: string, defaultDir: SortDir = 'desc') {
  const [sortKey, setSortKey] = useState(defaultKey);
  const [sortDir, setSortDir] = useState<SortDir>(defaultDir);

  const toggle = (key: string) => {
    if (key === sortKey) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sorted = [...data].sort((a, b) => {
    const av = (a as Record<string, unknown>)[sortKey];
    const bv = (b as Record<string, unknown>)[sortKey];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    const cmp = typeof av === 'string' ? av.localeCompare(bv as string) : (av as number) - (bv as number);
    return sortDir === 'asc' ? cmp : -cmp;
  });

  return { sorted, sortKey, sortDir, toggle };
}

// ── History Table ───────────────────────────────────────────────────────────

function HistoryTable({ history }: { history: TokenUsage['history'] }) {
  // Enrich rows with computed fields for sorting
  const enriched = history.map(row => {
    const totalInput = row.input_tokens + row.cache_read_tokens;
    return {
      ...row,
      cachePercent: totalInput > 0 ? (row.cache_read_tokens / totalInput) * 100 : 0,
      _time: row.created_at ? new Date(row.created_at).getTime() : row.id,
      _milestone: row.milestone_id ?? -1,
    };
  });

  const { sorted, sortKey, sortDir, toggle } = useSortable(enriched, '_time');

  return (
    <div className="overflow-auto max-h-[320px]">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-bg-secondary">
          <tr className="text-text-muted border-b border-border-subtle">
            <SortHeader label="Time" sortKey="_time" currentKey={sortKey} currentDir={sortDir} onSort={toggle} className="pr-3" />
            <SortHeader label="Milestone" sortKey="_milestone" currentKey={sortKey} currentDir={sortDir} onSort={toggle} className="px-2" />
            <SortHeader label="Phase" sortKey="phase" currentKey={sortKey} currentDir={sortDir} onSort={toggle} className="px-2" />
            <SortHeader label="Model" sortKey="model" currentKey={sortKey} currentDir={sortDir} onSort={toggle} className="px-2" />
            <SortHeader label="In" sortKey="input_tokens" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" className="px-2" />
            <SortHeader label="Out" sortKey="output_tokens" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" className="px-2" />
            <SortHeader label="Cached" sortKey="cache_read_tokens" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" className="px-2" />
            <SortHeader label="Cache %" sortKey="cachePercent" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" className="px-2" />
            <SortHeader label="Cost" sortKey="cost_usd" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" className="pl-2" />
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
              <tr
                key={row.id}
                className="border-b border-border-subtle/50 hover:bg-bg-tertiary/50 transition-colors"
              >
                <td className="py-2 pr-3 text-text-muted whitespace-nowrap">
                  {row.created_at
                    ? new Date(row.created_at).toLocaleTimeString()
                    : '—'}
                </td>
                <td className="py-2 px-2 text-text-secondary font-mono">
                  {row.milestone_id != null ? `M${row.milestone_id}` : '—'}
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
                <td className="text-right py-2 px-2 font-mono">
                  <span className={row.cachePercent >= 80 ? 'text-status-success' : row.cachePercent >= 50 ? 'text-accent-cyan' : 'text-text-muted'}>
                    {row.cachePercent.toFixed(1)}%
                  </span>
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
