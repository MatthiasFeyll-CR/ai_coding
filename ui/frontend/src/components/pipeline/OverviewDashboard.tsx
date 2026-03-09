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
    BeakerIcon,
    BugIcon,
    CheckCircle2Icon,
    CircleDotIcon,
    CoinsIcon,
    FolderIcon,
    Loader2Icon,
    ShieldCheckIcon,
    TargetIcon,
    TrendingUpIcon
} from 'lucide-react';

import type { MilestoneInfo, TestAnalytics as TestAnalyticsData } from '@/types';

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
      className="bg-bg-secondary rounded-xl border border-border-subtle p-5 flex flex-col gap-2"
    >
      <div className="flex items-center gap-2 text-text-muted">
        <div className={`p-2 rounded-lg bg-bg-tertiary ${accentClass}`}>
          {icon}
        </div>
        <span className="text-sm font-medium uppercase tracking-wider">{label}</span>
      </div>
      <p className={`text-2xl font-bold ${accentClass}`}>{value}</p>
      {subtitle && (
        <p className="text-text-muted text-sm">{subtitle}</p>
      )}
    </motion.div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

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

  const { project, progress, cost, quality } = overview;

  const allDone =
    progress.current_phase === 'complete' &&
    progress.completed_milestones === progress.total_milestones;

  // Pick gauge color based on status
  const gaugeColor = allDone
    ? '#10b981' // green
    : progress.failed_milestones > 0
    ? '#ef4444' // red
    : '#06b6d4'; // cyan

  // Compute a simple cost forecast for display
  const forecastTotal = (() => {
    if (progress.completed_milestones < 1 || progress.completed_milestones >= progress.total_milestones) return null;
    const phase0Cost = cost.by_milestone?.find((m) => m.id === 0)?.cost_usd ?? 0;
    const milestoneCost = cost.total_usd - phase0Cost;
    const remaining = progress.total_milestones - progress.completed_milestones;
    // Subtract phase0 milestone from completed count
    const completedNonZero = cost.by_milestone?.filter((m) => m.id !== 0).length ?? progress.completed_milestones;
    if (completedNonZero < 1) return null;
    const avgPerMs = milestoneCost / completedNonZero;
    return cost.total_usd + avgPerMs * remaining;
  })();

  // Test analytics stats
  const testRuns = testData?.summary.total_test_runs ?? 0;
  const passRate = testData?.summary.pass_rate ?? 0;

  return (
    <div className="space-y-5 h-full flex flex-col">
      {/* ── Row 1: Project+Progress (2/3) + Stat groups (1/3) ────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 flex-1 min-h-0">
        {/* Left: Project Info with embedded Progress Chart */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="lg:col-span-2 bg-bg-secondary rounded-xl border border-border-subtle p-6 flex flex-col min-h-[300px]"
        >
          <div className="flex items-center gap-2 mb-5">
            <FolderIcon className="w-5 h-5 text-accent-cyan" />
            <h3 className="text-lg font-semibold text-text-primary">Project</h3>
          </div>

          <div className="flex flex-col lg:flex-row gap-6 flex-1">
            {/* Project details (left) */}
            <div className="flex-1 space-y-3 overflow-y-auto">
              <div>
                <p className="text-text-muted text-sm">Name</p>
                <p className="text-text-primary font-semibold text-lg">{project.name}</p>
              </div>
              {project.description && (
                <div>
                  <p className="text-text-muted text-sm">Description</p>
                  <p className="text-text-secondary text-sm leading-relaxed">{project.description}</p>
                </div>
              )}
              <div>
                <p className="text-text-muted text-sm">Path</p>
                <p
                  className="text-text-secondary font-mono text-xs truncate"
                  title={project.root_path}
                >
                  {project.root_path}
                </p>
              </div>
              <div>
                <p className="text-text-muted text-sm">Scope</p>
                <p className="text-text-primary text-sm">
                  {project.total_milestones} milestones &middot; {project.total_stories} stories
                </p>
              </div>
            </div>

            {/* Progress gauge (right side within project box) */}
            <div className="flex flex-col items-center justify-center lg:min-w-[260px]">
              <SemiGauge
                value={progress.percentage}
                label={`${progress.completed_milestones} of ${progress.total_milestones} milestones`}
                color={gaugeColor}
                size={260}
              />
            </div>
          </div>
        </motion.div>

        {/* Right: Two groups of stat cards stacked vertically */}
        <div className="flex flex-col gap-3">
          {/* Group 1: Cost metrics */}
          <div className="space-y-3">
            <StatCard
              icon={<CoinsIcon className="w-5 h-5" />}
              label="Total Cost"
              value={formatCost(cost.total_usd)}
              subtitle={`${cost.by_milestone.length} milestone${cost.by_milestone.length !== 1 ? 's' : ''} billed`}
              accentClass="text-status-success"
            />

            {/* Budget card */}
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-bg-secondary rounded-xl border border-border-subtle p-4 flex flex-col gap-1.5"
            >
              <div className="flex items-center gap-2 text-text-muted">
                <div className={`p-1.5 rounded-lg bg-bg-tertiary ${
                  cost.budget_usd > 0 && cost.budget_pct >= 80
                    ? 'text-status-warning'
                    : cost.budget_usd > 0
                    ? 'text-accent-cyan'
                    : 'text-text-muted'
                }`}>
                  <TargetIcon className="w-4 h-4" />
                </div>
                <span className="text-sm font-medium uppercase tracking-wider">Budget</span>
              </div>
              {cost.budget_usd > 0 ? (
                <>
                  <p className={`text-xl font-bold ${
                    cost.budget_pct >= 90 ? 'text-status-error' : cost.budget_pct >= 80 ? 'text-status-warning' : 'text-accent-cyan'
                  }`}>
                    {cost.budget_pct.toFixed(1)}%
                  </p>
                  <div className="w-full bg-bg-tertiary rounded-full h-1.5">
                    <motion.div
                      className={`h-1.5 rounded-full ${
                        cost.budget_pct >= 90 ? 'bg-status-error' : cost.budget_pct >= 80 ? 'bg-status-warning' : 'bg-accent-cyan'
                      }`}
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min(100, cost.budget_pct)}%` }}
                      transition={{ duration: 0.8, ease: 'easeOut' }}
                    />
                  </div>
                  <p className="text-text-muted text-xs">
                    {formatCost(cost.total_usd)} of {formatCost(cost.budget_usd)}
                  </p>
                </>
              ) : (
                <p className="text-lg font-bold text-text-muted">No limit</p>
              )}
            </motion.div>

            {/* Cost Forecast */}
            <StatCard
              icon={<TrendingUpIcon className="w-5 h-5" />}
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

          {/* Group 2: Quality metrics */}
          <div className="space-y-3">
            <StatCard
              icon={<BugIcon className="w-5 h-5" />}
              label="Bugfix Cycles"
              value={String(quality.total_bugfix_cycles)}
              subtitle={
                quality.total_test_fix_cycles > 0
                  ? `+ ${quality.total_test_fix_cycles} test-fix cycles`
                  : quality.total_bugfix_cycles === 0
                  ? 'All passed first try'
                  : `${quality.milestones_with_bugfixes.length} milestones fixed`
              }
              accentClass={quality.total_bugfix_cycles === 0 ? 'text-status-success' : 'text-status-warning'}
            />

            <StatCard
              icon={<BeakerIcon className="w-5 h-5" />}
              label="Test Runs"
              value={String(testRuns)}
              subtitle={testRuns > 0 ? `across ${testData?.milestones.length ?? 0} milestones` : 'No tests yet'}
              accentClass="text-accent-cyan"
            />

            <StatCard
              icon={<ShieldCheckIcon className="w-5 h-5" />}
              label="Pass Rate"
              value={testRuns > 0 ? `${passRate.toFixed(1)}%` : '—'}
              subtitle={
                testRuns > 0
                  ? `${testData?.summary.passed ?? 0} passed · ${testData?.summary.failed ?? 0} failed`
                  : 'Awaiting QA runs'
              }
              accentClass={passRate >= 80 ? 'text-status-success' : passRate >= 50 ? 'text-status-warning' : testRuns > 0 ? 'text-status-error' : 'text-text-muted'}
            />
          </div>
        </div>
      </div>

      {/* ── Row 2: Current Position (bottom left) ──────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="lg:col-span-2 bg-bg-secondary rounded-xl border border-border-subtle p-6"
        >
          <div className="flex items-center gap-2 mb-4">
            <TargetIcon className="w-5 h-5 text-accent-green" />
            <h3 className="text-lg font-semibold text-text-primary">Current Position</h3>
          </div>

          {allDone ? (
            <div className="flex items-center gap-4 py-3">
              <CheckCircle2Icon className="w-10 h-10 text-status-success" />
              <div>
                <p className="text-status-success font-semibold text-lg">Pipeline Complete</p>
                <p className="text-text-muted text-sm">
                  {progress.total_milestones} milestones finished successfully
                </p>
              </div>
            </div>
          ) : (
            <div className="flex gap-8">
              <div>
                <p className="text-text-muted text-sm mb-1">Milestone</p>
                <p className="text-text-primary font-semibold text-lg">
                  M{progress.current_milestone}
                </p>
                <p className="text-text-secondary text-sm">
                  {progress.current_milestone_name}
                </p>
              </div>
              <div>
                <p className="text-text-muted text-sm mb-1">Phase</p>
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
                  <span className="text-accent-cyan font-medium text-lg">
                    {formatPhase(progress.current_phase)}
                  </span>
                </div>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
