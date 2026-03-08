/**
 * PhaseFSM — Accurate finite-state-machine visualisation for a single milestone.
 *
 * Backend truth (src/ralph_pipeline/runner.py):
 *   States:  pending → prd_generation → ralph_execution → qa_review → reconciliation → complete
 *   Catch-all: fail  (* → failed)
 *   Bugfix loop: qa_needs_fix  (qa_review → ralph_execution)
 *
 * Phase-0 (scaffolding milestone) has its own reduced FSM.
 *
 * Renders as an SVG-based graph with animated transitions, status indicators,
 * and the bugfix loop arc — no ReactFlow dependency.
 */

import type { MilestoneInfo } from '@/types';
import clsx from 'clsx';
import { motion } from 'framer-motion';
import {
    AlertTriangleIcon,
    CheckCircle2Icon,
    CircleDotIcon,
    Loader2Icon,
    PauseCircleIcon,
    XCircleIcon,
} from 'lucide-react';

/* ------------------------------------------------------------------ */
/*  FSM definition — mirrors runner.py exactly                         */
/* ------------------------------------------------------------------ */

interface FSMPhase {
  id: string;
  label: string;
  short: string;
}

const MAIN_PHASES: FSMPhase[] = [
  { id: 'pending', label: 'Pending', short: 'PND' },
  { id: 'prd_generation', label: 'PRD Generation', short: 'PRD' },
  { id: 'ralph_execution', label: 'Ralph Execution', short: 'EXEC' },
  { id: 'qa_review', label: 'QA Review', short: 'QA' },
  { id: 'reconciliation', label: 'Reconciliation', short: 'REC' },
  { id: 'complete', label: 'Complete', short: 'DONE' },
];

const PHASE0_PHASES: FSMPhase[] = [
  { id: 'pending', label: 'Pending', short: 'PND' },
  { id: 'phase0_scaffolding', label: 'Scaffolding', short: 'SCAF' },
  { id: 'phase0_test_infra', label: 'Test Infra', short: 'TEST' },
  { id: 'phase0_lifecycle', label: 'Lifecycle Verify', short: 'LIFE' },
  { id: 'complete', label: 'Complete', short: 'DONE' },
];

const PHASE_ORDER = new Map<string, number>();
MAIN_PHASES.forEach((p, i) => PHASE_ORDER.set(p.id, i));

const PHASE0_ORDER = new Map<string, number>();
PHASE0_PHASES.forEach((p, i) => PHASE0_ORDER.set(p.id, i));

/* ------------------------------------------------------------------ */
/*  Status helpers                                                     */
/* ------------------------------------------------------------------ */

type PhaseStatus = 'completed' | 'active' | 'paused' | 'failed' | 'pending';

function getPhaseStatus(
  phaseId: string,
  currentPhase: string,
  milestoneCompleted: boolean,
  pipelineStatus: string,
  orderMap: Map<string, number>
): PhaseStatus {
  if (currentPhase === 'failed') {
    const currentIdx = orderMap.get(phaseId) ?? -1;
    // Mark phases before the failure point as completed, the rest as failed/pending
    // We can't know exactly which phase failed, so show current state
    if (phaseId === 'complete') return 'pending';
    return currentIdx === 0 ? 'completed' : 'pending';
  }
  if (milestoneCompleted || currentPhase === 'complete') return 'completed';
  const currentIdx = orderMap.get(currentPhase) ?? -1;
  const phaseIdx = orderMap.get(phaseId) ?? -1;
  if (phaseIdx < currentIdx) return 'completed';
  if (phaseIdx === currentIdx) {
    return pipelineStatus === 'running' ? 'active' : 'paused';
  }
  return 'pending';
}

/* ------------------------------------------------------------------ */
/*  Status colors & icons                                              */
/* ------------------------------------------------------------------ */

const STATUS_COLORS: Record<PhaseStatus, { bg: string; border: string; text: string; dot: string }> = {
  completed: {
    bg: 'bg-status-success/10',
    border: 'border-status-success/60',
    text: 'text-status-success',
    dot: '#10b981',
  },
  active: {
    bg: 'bg-accent-cyan/10',
    border: 'border-accent-cyan/60',
    text: 'text-accent-cyan',
    dot: '#06b6d4',
  },
  paused: {
    bg: 'bg-text-muted/10',
    border: 'border-text-muted/40',
    text: 'text-text-muted',
    dot: '#6b7280',
  },
  failed: {
    bg: 'bg-status-error/10',
    border: 'border-status-error/60',
    text: 'text-status-error',
    dot: '#ef4444',
  },
  pending: {
    bg: 'bg-bg-tertiary/40',
    border: 'border-border-subtle',
    text: 'text-text-muted',
    dot: '#374151',
  },
};

function StatusIcon({ status, size = 14 }: { status: PhaseStatus; size?: number }) {
  const cls = STATUS_COLORS[status].text;
  const s = { width: size, height: size };

  switch (status) {
    case 'completed':
      return <CheckCircle2Icon className={cls} style={s} />;
    case 'active':
      return (
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
          className="flex items-center"
        >
          <Loader2Icon className={cls} style={s} />
        </motion.div>
      );
    case 'paused':
      return <PauseCircleIcon className={cls} style={s} />;
    case 'failed':
      return <XCircleIcon className={cls} style={s} />;
    default:
      return <CircleDotIcon className={cls} style={s} />;
  }
}

/* ------------------------------------------------------------------ */
/*  SVG arrow connectors                                               */
/* ------------------------------------------------------------------ */

interface ArrowProps {
  /** From node index to node index (within the phase array) */
  from: number;
  to: number;
  status: PhaseStatus;
  nodeWidth: number;
  nodeHeight: number;
  gapX: number;
  offsetY: number;
  animated?: boolean;
}

function StraightArrow({ from, to, status, nodeWidth, gapX, nodeHeight, offsetY, animated }: ArrowProps) {
  const x1 = from * (nodeWidth + gapX) + nodeWidth;
  const x2 = to * (nodeWidth + gapX);
  const y = offsetY + nodeHeight / 2;

  const color =
    status === 'completed'
      ? '#10b981'
      : status === 'active'
      ? '#06b6d4'
      : '#374151';

  return (
    <g>
      <line
        x1={x1}
        y1={y}
        x2={x2 - 6}
        y2={y}
        stroke={color}
        strokeWidth={2}
        strokeDasharray={animated ? '6 4' : undefined}
      >
        {animated && (
          <animate
            attributeName="stroke-dashoffset"
            from="0"
            to="-20"
            dur="0.8s"
            repeatCount="indefinite"
          />
        )}
      </line>
      {/* Arrowhead */}
      <polygon
        points={`${x2 - 6},${y - 4} ${x2},${y} ${x2 - 6},${y + 4}`}
        fill={color}
      />
    </g>
  );
}

/* ------------------------------------------------------------------ */
/*  Bugfix loop arc (qa_review → ralph_execution)                      */
/* ------------------------------------------------------------------ */

interface BugfixArcProps {
  ralphIdx: number;
  qaIdx: number;
  nodeWidth: number;
  nodeHeight: number;
  gapX: number;
  offsetY: number;
  active: boolean;
  cycleInfo: string;
}

function BugfixArc({
  ralphIdx,
  qaIdx,
  nodeWidth,
  gapX,
  nodeHeight,
  offsetY,
  active,
  cycleInfo,
}: BugfixArcProps) {
  // Arc from qa_review bottom → ralph_execution bottom
  const qaCenter = qaIdx * (nodeWidth + gapX) + nodeWidth / 2;
  const ralphCenter = ralphIdx * (nodeWidth + gapX) + nodeWidth / 2;
  const topY = offsetY + nodeHeight + 8;
  const bottomY = topY + 28;
  const midX = (qaCenter + ralphCenter) / 2;

  const color = active ? '#f59e0b' : '#374151';

  const path = `M ${qaCenter} ${topY} C ${qaCenter} ${bottomY}, ${ralphCenter} ${bottomY}, ${ralphCenter} ${topY}`;

  return (
    <g>
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeDasharray={active ? '5 3' : '4 4'}
        opacity={active ? 1 : 0.5}
      >
        {active && (
          <animate
            attributeName="stroke-dashoffset"
            from="0"
            to="-16"
            dur="0.6s"
            repeatCount="indefinite"
          />
        )}
      </path>
      {/* Arrowhead pointing up into ralph_execution */}
      <polygon
        points={`${ralphCenter - 3},${topY + 4} ${ralphCenter},${topY - 1} ${ralphCenter + 3},${topY + 4}`}
        fill={color}
        opacity={active ? 1 : 0.5}
      />
      {/* Label */}
      <text
        x={midX}
        y={bottomY + 12}
        textAnchor="middle"
        fontSize={10}
        fill={active ? '#f59e0b' : '#6b7280'}
        fontFamily="JetBrains Mono, monospace"
      >
        {cycleInfo}
      </text>
    </g>
  );
}

/* ------------------------------------------------------------------ */
/*  Fail state indicator                                               */
/* ------------------------------------------------------------------ */

interface FailIndicatorProps {
  nodeWidth: number;
  nodeHeight: number;
  gapX: number;
  offsetY: number;
  totalNodes: number;
  isFailed: boolean;
}

function FailIndicator({ nodeWidth, gapX, offsetY, totalNodes, isFailed }: FailIndicatorProps) {
  const totalWidth = totalNodes * nodeWidth + (totalNodes - 1) * gapX;
  const x = totalWidth / 2;
  const y = offsetY - 20;

  if (!isFailed) return null;

  return (
    <g>
      <motion.g
        initial={{ opacity: 0, y: 5 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <rect
          x={x - 40}
          y={y - 10}
          width={80}
          height={20}
          rx={4}
          fill="rgba(239, 68, 68, 0.15)"
          stroke="#ef4444"
          strokeWidth={1}
          strokeDasharray="4 2"
        />
        <text
          x={x}
          y={y + 4}
          textAnchor="middle"
          fontSize={11}
          fill="#ef4444"
          fontWeight={600}
          fontFamily="Inter, system-ui, sans-serif"
        >
          FAILED
        </text>
      </motion.g>
    </g>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

interface PhaseFSMProps {
  milestone: MilestoneInfo;
  maxBugfixCycles: number;
  pipelineStatus: string;
  selectedCycle: number | null;
  onSelectCycle: (cycle: number | null) => void;
}

export function PhaseFSM({
  milestone,
  maxBugfixCycles,
  pipelineStatus,
  selectedCycle,
  onSelectCycle,
}: PhaseFSMProps) {
  const isCompleted = !!milestone.completed_at;
  const isFailed = milestone.phase === 'failed';
  const isPhase0 = milestone.id === 0;
  const phases = isPhase0 ? PHASE0_PHASES : MAIN_PHASES;
  const orderMap = isPhase0 ? PHASE0_ORDER : PHASE_ORDER;
  const hasBugfixCycles = milestone.bugfix_cycle > 0;

  // Layout constants
  const NODE_W = 130;
  const NODE_H = 48;
  const GAP_X = 32;
  const OFFSET_Y = 28;
  const totalWidth = phases.length * NODE_W + (phases.length - 1) * GAP_X;
  const svgHeight = isPhase0 ? 90 : hasBugfixCycles || !isPhase0 ? 120 : 90;
  const svgWidth = totalWidth + 16;

  // Find indices for bugfix arc
  const ralphIdx = phases.findIndex((p) => p.id === 'ralph_execution');
  const qaIdx = phases.findIndex((p) => p.id === 'qa_review');

  return (
    <div className="flex flex-col gap-2">
      {/* FSM Graph */}
      <div className="relative overflow-x-auto">
        <div className="min-w-fit px-2">
          {/* SVG arrows layer */}
          <svg
            width={svgWidth}
            height={svgHeight}
            viewBox={`-8 0 ${svgWidth} ${svgHeight}`}
            className="absolute top-0 left-2 pointer-events-none"
          >
            {/* Transition arrows */}
            {phases.slice(0, -1).map((phase, i) => {
              const status = getPhaseStatus(
                phase.id,
                milestone.phase,
                isCompleted,
                pipelineStatus,
                orderMap
              );
              return (
                <StraightArrow
                  key={`${phase.id}-arrow`}
                  from={i}
                  to={i + 1}
                  status={status}
                  nodeWidth={NODE_W}
                  nodeHeight={NODE_H}
                  gapX={GAP_X}
                  offsetY={OFFSET_Y}
                  animated={status === 'active'}
                />
              );
            })}

            {/* Bugfix loop arc */}
            {!isPhase0 && ralphIdx >= 0 && qaIdx >= 0 && (
              <BugfixArc
                ralphIdx={ralphIdx}
                qaIdx={qaIdx}
                nodeWidth={NODE_W}
                nodeHeight={NODE_H}
                gapX={GAP_X}
                offsetY={OFFSET_Y}
                active={hasBugfixCycles && milestone.phase === 'qa_review'}
                cycleInfo={
                  hasBugfixCycles
                    ? `bugfix ${milestone.bugfix_cycle}/${maxBugfixCycles}`
                    : 'qa_needs_fix'
                }
              />
            )}

            {/* Fail indicator */}
            <FailIndicator
              nodeWidth={NODE_W}
              nodeHeight={NODE_H}
              gapX={GAP_X}
              offsetY={OFFSET_Y}
              totalNodes={phases.length}
              isFailed={isFailed}
            />
          </svg>

          {/* Phase nodes */}
          <div
            className="relative flex items-start gap-0"
            style={{ paddingTop: OFFSET_Y }}
          >
            {phases.map((phase, i) => {
              const status = isFailed
                ? 'failed'
                : getPhaseStatus(
                    phase.id,
                    milestone.phase,
                    isCompleted,
                    pipelineStatus,
                    orderMap
                  );
              const colors = STATUS_COLORS[status];
              const isActive = status === 'active';

              return (
                <motion.div
                  key={phase.id}
                  className={clsx(
                    'relative flex flex-col items-center justify-center rounded-lg border-2 transition-all',
                    colors.bg,
                    colors.border,
                    isActive && 'shadow-glow-cyan'
                  )}
                  style={{
                    width: NODE_W,
                    height: NODE_H,
                    marginRight: i < phases.length - 1 ? GAP_X : 0,
                  }}
                  animate={
                    isActive
                      ? {
                          boxShadow: [
                            '0 0 8px rgba(6, 182, 212, 0.2)',
                            '0 0 16px rgba(6, 182, 212, 0.4)',
                            '0 0 8px rgba(6, 182, 212, 0.2)',
                          ],
                          transition: { duration: 2, repeat: Infinity },
                        }
                      : {}
                  }
                >
                  <div className="flex items-center gap-1.5">
                    <StatusIcon status={status} size={14} />
                    <span
                      className={clsx(
                        'text-xs font-semibold whitespace-nowrap',
                        colors.text
                      )}
                    >
                      {phase.label}
                    </span>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Status summary bar */}
      <div className="flex items-center gap-3 px-2">
        <PhaseProgressBar
          phases={phases}
          currentPhase={milestone.phase}
          isCompleted={isCompleted}
          isFailed={isFailed}
          pipelineStatus={pipelineStatus}
          orderMap={orderMap}
        />
      </div>

      {/* Bugfix cycle selector */}
      {hasBugfixCycles && (
        <div className="flex items-center gap-2 px-2">
          <AlertTriangleIcon className="w-3.5 h-3.5 text-status-warning shrink-0" />
          <span className="text-xs text-text-muted mr-1">Bugfix Cycles:</span>
          <button
            onClick={() => onSelectCycle(null)}
            className={clsx(
              'px-2.5 py-0.5 text-xs rounded-md transition-colors',
              selectedCycle === null
                ? 'bg-accent-cyan/20 text-accent-cyan'
                : 'bg-bg-tertiary text-text-secondary hover:bg-bg-hover'
            )}
          >
            All
          </button>
          {Array.from({ length: milestone.bugfix_cycle }, (_, i) => i + 1).map(
            (cycle) => (
              <button
                key={cycle}
                onClick={() => onSelectCycle(cycle)}
                className={clsx(
                  'px-2.5 py-0.5 text-xs rounded-md transition-colors',
                  selectedCycle === cycle
                    ? 'bg-status-warning/20 text-status-warning'
                    : 'bg-bg-tertiary text-text-secondary hover:bg-bg-hover'
                )}
              >
                #{cycle}
              </button>
            )
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Phase progress bar                                                 */
/* ------------------------------------------------------------------ */

function PhaseProgressBar({
  phases,
  currentPhase,
  isCompleted,
  isFailed,
  pipelineStatus,
  orderMap,
}: {
  phases: FSMPhase[];
  currentPhase: string;
  isCompleted: boolean;
  isFailed: boolean;
  pipelineStatus: string;
  orderMap: Map<string, number>;
}) {
  const completedCount = phases.filter(
    (p) =>
      getPhaseStatus(p.id, currentPhase, isCompleted, pipelineStatus, orderMap) ===
      'completed'
  ).length;
  const progress = isCompleted ? 100 : isFailed ? 0 : (completedCount / phases.length) * 100;

  return (
    <div className="flex-1 flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-bg-tertiary overflow-hidden">
        <motion.div
          className={clsx(
            'h-full rounded-full',
            isFailed ? 'bg-status-error' : 'bg-status-success'
          )}
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>
      <span className="text-[10px] text-text-muted font-mono shrink-0">
        {isFailed
          ? 'FAILED'
          : isCompleted
          ? 'COMPLETE'
          : `${completedCount}/${phases.length}`}
      </span>
    </div>
  );
}
