/**
 * OverviewDashboard — distilled project overview with visual gauges.
 *
 * Focuses on project-global information only:
 * - Progress gauge (180° semicircle)
 * - Current position (milestone + phase)
 * - Cost summary
 * - Quality / bugfix summary
 */

import { pipelineApi } from '@/api/client';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  AlertTriangleIcon,
  BeakerIcon,
  BugIcon,
  CheckCircle2Icon,
  CircleDotIcon,
  ClockIcon,
  CoinsIcon,
  FolderIcon,
  Loader2Icon,
  ShieldCheckIcon,
  TargetIcon,
  TimerIcon,
  TrendingUpIcon
} from 'lucide-react';

import { notify } from '@/lib/notify';
import type { MilestoneInfo, TestAnalytics as TestAnalyticsData } from '@/types';
import { useEffect, useRef, useState } from 'react';

interface OverviewDashboardProps {
  projectId: number;
  milestones: MilestoneInfo[];
  pipelineStatus: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatCost(usd: number): string {
  if (usd === 0) return '$0.00';
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  if (usd < 1) return `$${usd.toFixed(3)}`;
  return `$${usd.toFixed(2)}`;
}

function formatPhase(phase: string): string {
  const map: Record<string, string> = {
    pending: 'Pending',
    prd_generation: 'PRD Generation',
    ralph_execution: 'Implementation',
    qa_review: 'QA Review',
    reconciliation: 'Reconciliation',
    complete: 'Complete',
    failed: 'Failed',
    phase0_scaffolding: 'Scaffolding',
    phase0_test_infra: 'Test Infra',
    phase0_lifecycle: 'Lifecycle',
  };
  return map[phase] || phase;
}

// ── 180° Semicircle Gauge ─────────────────────────────────────────────────────

function SemiGauge({
  value,
  label,
  color = '#06b6d4',
  size = 180,
}: {
  value: number; // 0-100
  label: string;
  color?: string;
  size?: number;
}) {
  const clampedValue = Math.min(100, Math.max(0, value));
  const strokeWidth = 14;
  const radius = (size - strokeWidth) / 2;
  const circumference = Math.PI * radius; // Half circle
  const offset = circumference - (clampedValue / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg
        width={size}
        height={size / 2 + 16}
        viewBox={`0 0 ${size} ${size / 2 + 16}`}
        className="overflow-visible"
      >
        {/* Track */}
        <path
          d={`M ${strokeWidth / 2} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${size / 2}`}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          className="text-bg-tertiary"
        />
        {/* Filled arc */}
        <motion.path
          d={`M ${strokeWidth / 2} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${size / 2}`}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: 'easeOut' }}
        />
        {/* Center number */}
        <text
          x={size / 2}
          y={size / 2 - 8}
          textAnchor="middle"
          className="fill-text-primary text-3xl font-bold"
          fontSize="32"
          fontWeight="700"
        >
          {Math.round(clampedValue)}%
        </text>
        {/* Label */}
        <text
          x={size / 2}
          y={size / 2 + 14}
          textAnchor="middle"
          className="fill-text-muted"
          fontSize="11"
        >
          {label}
        </text>
      </svg>
    </div>
  );
}

// ── Stat Card ─────────────────────────────────────────────────────────────────

function StatCard({
  icon,
  label,
  value,
  subtitle,
  accentClass,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  subtitle?: string;
  accentClass: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-bg-secondary rounded-xl border border-border-subtle p-3 flex flex-col gap-1"
    >
      <div className="flex items-center gap-2 text-text-muted">
        <div className={`p-1.5 rounded-lg bg-bg-tertiary ${accentClass}`}>
          {icon}
        </div>
        <span className="text-xs font-medium uppercase tracking-wider">{label}</span>
      </div>
      <p className={`text-xl font-bold ${accentClass}`}>{value}</p>
      {subtitle && (
        <p className="text-text-muted text-xs">{subtitle}</p>
      )}
    </motion.div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

// ── Time helpers ──────────────────────────────────────────────────────────────

function formatDuration(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = Math.floor(totalSeconds % 60);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/** Live stopwatch that ticks every second. */
function ElapsedClock({ startedAt }: { startedAt: string | null }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!startedAt) { setElapsed(0); return; }
    const start = new Date(startedAt).getTime();
    if (Number.isNaN(start)) { setElapsed(0); return; }

    const tick = () => setElapsed(Math.max(0, Math.floor((Date.now() - start) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  if (!startedAt) return <span className="text-text-muted">—</span>;

  return (
    <span className="font-mono text-lg font-bold text-accent-cyan tabular-nums tracking-wider">
      {formatDuration(elapsed)}
    </span>
  );
}

/** Compute time forecast from completed milestone durations + remaining story counts. */
function computeTimeForecast(
  milestoneDetails: Array<{ id: number; stories: number; completed: boolean; started_at?: string; completed_at?: string }>,
  pipelineStartedAt: string | null,
): { forecastSeconds: number; confidence: 'low' | 'medium' | 'high' } | null {
  // Gather completed non-phase0 milestones with valid timestamps
  const completed: Array<{ stories: number; durationSec: number }> = [];
  for (const m of milestoneDetails) {
    if (m.id === 0 || !m.completed || !m.started_at || !m.completed_at) continue;
    const dur = (new Date(m.completed_at).getTime() - new Date(m.started_at).getTime()) / 1000;
    if (dur > 0 && m.stories > 0) {
      completed.push({ stories: m.stories, durationSec: dur });
    }
  }
  if (completed.length === 0) return null;

  // Weighted average seconds per story
  const totalStories = completed.reduce((s, c) => s + c.stories, 0);
  const totalDur = completed.reduce((s, c) => s + c.durationSec, 0);
  const secPerStory = totalDur / totalStories;

  // Remaining milestones
  const remaining = milestoneDetails.filter((m) => m.id !== 0 && !m.completed);
  const remainingStories = remaining.reduce((s, m) => s + (m.stories || 1), 0);

  // Elapsed so far
  const elapsedSoFar = pipelineStartedAt
    ? Math.max(0, (Date.now() - new Date(pipelineStartedAt).getTime()) / 1000)
    : totalDur;

  const forecastSeconds = elapsedSoFar + secPerStory * remainingStories;
  const confidence = completed.length >= 3 ? 'high' : completed.length >= 2 ? 'medium' : 'low';

  return { forecastSeconds, confidence };
}

// ── Main export ───────────────────────────────────────────────────────────────

export function OverviewDashboard({
  projectId,
  milestones,
  pipelineStatus,
}: OverviewDashboardProps) {
  const { data: overview, isLoading } = useQuery({
    queryKey: ['overview', projectId],
    queryFn: () => pipelineApi.getOverview(projectId).then((r) => r.data),
    enabled: !!projectId,
    refetchInterval: 2000,
  });

  // Fetch test analytics for test count / pass rate
  const { data: testData } = useQuery<TestAnalyticsData>({
    queryKey: ['test-analytics', projectId],
    queryFn: () => pipelineApi.getTestAnalytics(projectId).then((r) => r.data),
    enabled: !!projectId,
    refetchInterval: 5000,
  });

  // Budget exceeded warning — notify once (hook must be before early return)
  const budgetWarningFired = useRef(false);

  const { project, progress, cost, quality } = overview ?? {} as Record<string, any>;

  // Compute a simple cost forecast for display
  const forecastTotal = (() => {
    if (!overview) return null;
    if (progress.completed_milestones < 1 || progress.completed_milestones >= progress.total_milestones) return null;
    const phase0Cost = cost.by_milestone?.find((m: any) => m.id === 0)?.cost_usd ?? 0;
    const milestoneCost = cost.total_usd - phase0Cost;
    const remaining = progress.total_milestones - progress.completed_milestones;
    // Subtract phase0 milestone from completed count
    const completedNonZero = cost.by_milestone?.filter((m: any) => m.id !== 0).length ?? progress.completed_milestones;
    if (completedNonZero < 1) return null;
    const avgPerMs = milestoneCost / completedNonZero;
    return cost.total_usd + avgPerMs * remaining;
  })();

  const isForecastOverBudget = !!(forecastTotal && cost?.budget_usd > 0 && forecastTotal > cost.budget_usd);

  useEffect(() => {
    if (isForecastOverBudget && !budgetWarningFired.current) {
      budgetWarningFired.current = true;
      notify('warning', `Cost forecast (${formatCost(forecastTotal!)}) exceeds budget (${formatCost(cost.budget_usd)})`);
    }
  }, [isForecastOverBudget, forecastTotal, cost?.budget_usd]);

  // Time tracking
  const pipelineStartedAt: string | null = overview?.pipeline?.started_at ?? null;
  const timeForecast = computeTimeForecast(
    overview?.milestone_details ?? [],
    pipelineStartedAt,
  );

  if (isLoading || !overview) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-text-muted">
          <div className="w-5 h-5 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
          Loading overview...
        </div>
      </div>
    );
  }

  const allDone =
    progress.current_phase === 'complete' &&
    progress.completed_milestones === progress.total_milestones;

  // Pick gauge color based on status
  const gaugeColor = allDone
    ? '#10b981' // green
    : progress.failed_milestones > 0
    ? '#ef4444' // red
    : '#06b6d4'; // cyan

  // Test analytics stats
  const testRuns = testData?.summary.total_test_runs ?? 0;
  const passRate = testData?.summary.pass_rate ?? 0;

  return (
    <div className="space-y-3 h-full flex flex-col">
      {/* ── Single row: Project+Position (2/3) + Stats+Time (1/3) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 flex-1 min-h-0">
        {/* Left: Project Info with embedded Progress Chart + Current Position */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="lg:col-span-2 bg-bg-secondary rounded-xl border border-border-subtle p-5 flex flex-col"
        >
          <div className="flex items-center gap-2 mb-3">
            <FolderIcon className="w-5 h-5 text-accent-cyan" />
            <h3 className="text-lg font-semibold text-text-primary">Project</h3>
          </div>

          <div className="flex flex-col lg:flex-row gap-4 flex-1">
            {/* Project details (left — 3/5 width) */}
            <div className="flex-[3] space-y-2 overflow-y-auto min-w-0">
              <div>
                <p className="text-text-muted text-xs">Name</p>
                <p className="text-text-primary font-semibold text-base">{project.name}</p>
              </div>
              {project.description && (
                <div>
                  <p className="text-text-muted text-xs">Description</p>
                  <p className="text-text-secondary text-sm leading-relaxed">{project.description}</p>
                </div>
              )}
              <div>
                <p className="text-text-muted text-xs">Path</p>
                <p
                  className="text-text-secondary font-mono text-xs truncate"
                  title={project.root_path}
                >
                  {project.root_path}
                </p>
              </div>
              <div>
                <p className="text-text-muted text-xs">Scope</p>
                <p className="text-text-primary text-sm">
                  {project.total_milestones} milestones &middot; {project.total_stories} stories
                </p>
              </div>
            </div>

            {/* Progress gauge (right — 2/5 width) */}
            <div className="flex-[2] flex flex-col items-center justify-center min-w-[200px]">
              <h4 className="text-xs font-semibold text-text-primary mb-1 uppercase tracking-wider">Progress</h4>
              <SemiGauge
                value={progress.percentage}
                label={`${progress.completed_milestones} of ${progress.total_milestones} milestones`}
                color={gaugeColor}
                size={220}
              />
            </div>
          </div>

          {/* Current Position — below project details */}
          <div className="mt-3 pt-3 border-t border-border-subtle">
            <div className="flex items-center gap-2 mb-2">
              <TargetIcon className="w-4 h-4 text-accent-green" />
              <h3 className="text-sm font-semibold text-text-primary">Current Position</h3>
            </div>

            {allDone ? (
              <div className="flex items-center gap-3 py-1">
                <CheckCircle2Icon className="w-8 h-8 text-status-success" />
                <div>
                  <p className="text-status-success font-semibold">Pipeline Complete</p>
                  <p className="text-text-muted text-xs">
                    {progress.total_milestones} milestones finished successfully
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex gap-6">
                <div>
                  <p className="text-text-muted text-xs mb-0.5">Milestone</p>
                  <p className="text-text-primary font-semibold">
                    M{progress.current_milestone}
                  </p>
                  <p className="text-text-secondary text-xs">
                    {progress.current_milestone_name}
                  </p>
                </div>
                <div>
                  <p className="text-text-muted text-xs mb-0.5">Phase</p>
                  <div className="flex items-center gap-2">
                    {pipelineStatus === 'running' ? (
                      <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
                      >
                        <Loader2Icon className="w-4 h-4 text-accent-cyan" />
                      </motion.div>
                    ) : (
                      <CircleDotIcon className="w-4 h-4 text-accent-cyan" />
                    )}
                    <span className="text-accent-cyan font-medium">
                      {formatPhase(progress.current_phase)}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </motion.div>

        {/* Right: Stat cards + Time tracker in single scrollable column */}
        <div className="flex flex-col gap-2 overflow-y-auto min-h-0">
          {/* Cost metrics */}
          <StatCard
            icon={<CoinsIcon className="w-4 h-4" />}
            label="Total Cost"
            value={formatCost(cost.total_usd)}
            subtitle={`${cost.by_milestone.length} milestone${cost.by_milestone.length !== 1 ? 's' : ''} billed`}
            accentClass="text-status-success"
          />

          {/* Budget card */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-bg-secondary rounded-xl border border-border-subtle p-3 flex flex-col gap-1"
          >
            <div className="flex items-center gap-2 text-text-muted">
              <div className={`p-1.5 rounded-lg bg-bg-tertiary ${
                cost.budget_usd > 0 && cost.budget_pct >= 80
                  ? 'text-status-warning'
                  : cost.budget_usd > 0
                  ? 'text-accent-cyan'
                  : 'text-text-muted'
              }`}>
                <TargetIcon className="w-3.5 h-3.5" />
              </div>
              <span className="text-xs font-medium uppercase tracking-wider">Budget</span>
            </div>
            {cost.budget_usd > 0 ? (
              <>
                <div className="flex items-center gap-2">
                  <p className={`text-lg font-bold ${
                    cost.budget_pct >= 90 ? 'text-status-error' : cost.budget_pct >= 80 ? 'text-status-warning' : 'text-accent-cyan'
                  }`}>
                    {cost.budget_pct.toFixed(1)}%
                  </p>
                  <p className="text-text-muted text-xs">
                    {formatCost(cost.total_usd)} of {formatCost(cost.budget_usd)}
                  </p>
                </div>
                <div className="w-full bg-bg-tertiary rounded-full h-1">
                  <motion.div
                    className={`h-1 rounded-full ${
                      cost.budget_pct >= 90 ? 'bg-status-error' : cost.budget_pct >= 80 ? 'bg-status-warning' : 'bg-accent-cyan'
                    }`}
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.min(100, cost.budget_pct)}%` }}
                    transition={{ duration: 0.8, ease: 'easeOut' }}
                  />
                </div>
              </>
            ) : (
              <p className="text-sm font-bold text-text-muted">No limit</p>
            )}
          </motion.div>

          {/* Cost Forecast */}
          <div className="relative">
            {isForecastOverBudget && (
              <div className="absolute -top-1 -right-1 z-10 flex items-center gap-1 px-1.5 py-0.5 bg-status-warning rounded-full shadow-md">
                <AlertTriangleIcon className="w-3 h-3 text-white" />
                <span className="text-[9px] font-bold text-white uppercase">Over Budget</span>
              </div>
            )}
            <StatCard
              icon={<TrendingUpIcon className="w-4 h-4" />}
              label="Cost Forecast"
              value={forecastTotal ? formatCost(forecastTotal) : '—'}
              subtitle={
                forecastTotal
                  ? forecastTotal > cost.budget_usd && cost.budget_usd > 0
                    ? `⚠ +${formatCost(forecastTotal - cost.budget_usd)} over budget`
                    : 'Projected total spend'
                  : 'Needs completed milestones'
              }
              accentClass={
                forecastTotal && cost.budget_usd > 0 && forecastTotal > cost.budget_usd
                  ? 'text-status-warning'
                  : 'text-accent-purple'
              }
            />
          </div>

          {/* Quality metrics — inline row */}
          <div className="grid grid-cols-3 gap-2">
            <StatCard
              icon={<BugIcon className="w-4 h-4" />}
              label="Bugfixes"
              value={String(quality.total_bugfix_cycles)}
              accentClass={quality.total_bugfix_cycles === 0 ? 'text-status-success' : 'text-status-warning'}
            />
            <StatCard
              icon={<BeakerIcon className="w-4 h-4" />}
              label="Tests"
              value={String(testRuns)}
              accentClass="text-accent-cyan"
            />
            <StatCard
              icon={<ShieldCheckIcon className="w-4 h-4" />}
              label="Pass Rate"
              value={testRuns > 0 ? `${passRate.toFixed(0)}%` : '—'}
              accentClass={passRate >= 80 ? 'text-status-success' : passRate >= 50 ? 'text-status-warning' : testRuns > 0 ? 'text-status-error' : 'text-text-muted'}
            />
          </div>

          {/* Time Tracker — compact */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-bg-secondary rounded-xl border border-border-subtle p-3 flex items-center gap-4"
          >
            <div className="flex-1">
              <div className="flex items-center gap-1.5 mb-1">
                <ClockIcon className="w-3.5 h-3.5 text-accent-cyan" />
                <span className="text-xs font-medium uppercase tracking-wider text-text-muted">Time Spent</span>
              </div>
              <ElapsedClock startedAt={pipelineStartedAt} />
            </div>
            <div className="border-l border-border-subtle pl-4 flex-1">
              <div className="flex items-center gap-1.5 mb-1">
                <TimerIcon className="w-3.5 h-3.5 text-accent-purple" />
                <span className="text-xs font-medium uppercase tracking-wider text-text-muted">Est. Total</span>
              </div>
              {timeForecast ? (
                <>
                  <p className="font-mono text-lg font-bold text-accent-purple tabular-nums">
                    {formatDuration(timeForecast.forecastSeconds)}
                  </p>
                  <p className="text-text-muted text-[10px]">
                    ~{timeForecast.confidence === 'high' ? '3+ ms' : timeForecast.confidence === 'medium' ? '2 ms' : '1 ms'} sample
                  </p>
                </>
              ) : (
                <p className="text-sm font-bold text-text-muted">—</p>
              )}
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
