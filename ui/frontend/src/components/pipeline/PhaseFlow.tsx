import type { MilestoneInfo } from '@/types';
import clsx from 'clsx';
import { motion } from 'framer-motion';
import { CheckCircle2Icon, Loader2Icon, PauseCircleIcon } from 'lucide-react';
import { useMemo } from 'react';
import ReactFlow, {
  type Edge,
  Handle,
  type Node,
  type NodeProps,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';

const PHASES = [
  { id: 'prd_generation', label: 'PRD Generation' },
  { id: 'ralph_execution', label: 'Ralph Execution' },
  { id: 'qa_review', label: 'QA Review' },
  { id: 'merge_verify', label: 'Merge & Verify' },
  { id: 'reconciliation', label: 'Reconciliation' },
] as const;

const PHASE_ORDER: Record<string, number> = {};
PHASES.forEach((p, i) => {
  PHASE_ORDER[p.id] = i;
});

interface PhaseFlowProps {
  milestone: MilestoneInfo;
  maxBugfixCycles: number;
  pipelineStatus: string;
  selectedCycle: number | null;
  onSelectCycle: (cycle: number | null) => void;
}

type PhaseStatus = 'completed' | 'active' | 'paused' | 'pending';

function getPhaseStatus(
  phaseId: string,
  currentPhase: string,
  milestoneCompleted: boolean,
  pipelineStatus: string
): PhaseStatus {
  if (milestoneCompleted) return 'completed';

  const currentIdx = PHASE_ORDER[currentPhase] ?? -1;
  const phaseIdx = PHASE_ORDER[phaseId] ?? -1;

  if (phaseIdx < currentIdx) return 'completed';
  if (phaseIdx === currentIdx) {
    return pipelineStatus === 'running' ? 'active' : 'paused';
  }
  return 'pending';
}

interface PhaseNodeData {
  label: string;
  status: PhaseStatus;
}

function PhaseNode({ data }: NodeProps<PhaseNodeData>) {
  const borderColor: Record<PhaseStatus, string> = {
    completed: 'border-status-success',
    active: 'border-accent-cyan',
    paused: 'border-text-muted',
    pending: 'border-border-subtle',
  };

  return (
    <div
      className={clsx(
        'px-5 py-3 rounded-lg border-2 bg-bg-tertiary whitespace-nowrap min-w-[130px]',
        borderColor[data.status]
      )}
    >
      <Handle type="target" position={Position.Left} className="!opacity-0 !w-0 !h-0" />
      <div className="flex items-center justify-center gap-3">
        <span className="font-medium text-sm">{data.label}</span>
        <PhaseStatusIcon status={data.status} />
      </div>
      <Handle type="source" position={Position.Right} className="!opacity-0 !w-0 !h-0" />
    </div>
  );
}

function PhaseStatusIcon({ status }: { status: PhaseStatus }) {
  if (status === 'completed') {
    return <CheckCircle2Icon className="w-4 h-4 text-status-success flex-shrink-0" />;
  }
  if (status === 'active') {
    return (
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
      >
        <Loader2Icon className="w-4 h-4 text-accent-cyan flex-shrink-0" />
      </motion.div>
    );
  }
  if (status === 'paused') {
    return <PauseCircleIcon className="w-4 h-4 text-text-muted flex-shrink-0" />;
  }
  return null;
}

const nodeTypes = { phase: PhaseNode };

export function PhaseFlow({
  milestone,
  maxBugfixCycles,
  pipelineStatus,
  selectedCycle,
  onSelectCycle,
}: PhaseFlowProps) {
  const isCompleted = !!milestone.completed_at;
  const hasBugfixCycles = milestone.bugfix_cycle > 0;

  const { nodes, edges } = useMemo(() => {
    const NODE_WIDTH = 150;
    const NODE_GAP = 30;

    const nodes: Node<PhaseNodeData>[] = PHASES.map((phase, index) => ({
      id: phase.id,
      type: 'phase',
      position: { x: index * (NODE_WIDTH + NODE_GAP), y: 40 },
      data: {
        label: phase.label,
        status: getPhaseStatus(phase.id, milestone.phase, isCompleted, pipelineStatus),
      },
      draggable: false,
      selectable: false,
    }));

    const edges: Edge[] = PHASES.slice(0, -1).map((phase, index) => {
      const nextPhase = PHASES[index + 1];
      const phaseStatus = getPhaseStatus(phase.id, milestone.phase, isCompleted, pipelineStatus);
      return {
        id: `${phase.id}-${nextPhase.id}`,
        source: phase.id,
        target: nextPhase.id,
        animated: phaseStatus === 'active',
        style: {
          stroke:
            phaseStatus === 'completed'
              ? 'var(--color-status-success, #22c55e)'
              : 'var(--color-border-subtle, #374151)',
        },
      };
    });

    // Add QA → Ralph backloop edge if bugfix cycles occurred
    if (hasBugfixCycles) {
      edges.push({
        id: 'qa-bugfix-loop',
        source: 'qa_review',
        target: 'ralph_execution',
        type: 'smoothstep',
        animated: milestone.phase === 'qa_review' && pipelineStatus === 'running',
        label: `QA fix cycle ${milestone.bugfix_cycle} of ${maxBugfixCycles}`,
        labelStyle: { fontSize: 10, fill: 'var(--color-text-muted, #9ca3af)' },
        labelBgStyle: { fill: 'var(--color-bg-secondary, #1e1e2e)', fillOpacity: 0.9 },
        labelBgPadding: [6, 4] as [number, number],
        labelBgBorderRadius: 4,
        style: {
          stroke: 'var(--color-status-warning, #f59e0b)',
          strokeDasharray: '5 5',
        },
        sourceHandle: null,
        targetHandle: null,
      });
    }

    return { nodes, edges };
  }, [milestone, isCompleted, hasBugfixCycles, maxBugfixCycles, pipelineStatus]);

  return (
    <div className="flex flex-col gap-3">
      <div className="h-[120px] rf-static">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.25, maxZoom: 1.5 }}
          panOnDrag={false}
          panOnScroll={false}
          zoomOnScroll={false}
          zoomOnPinch={false}
          zoomOnDoubleClick={false}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
        />
      </div>

      {/* Bugfix cycle tabs */}
      {hasBugfixCycles && (
        <div className="flex items-center gap-2 px-2 pb-2">
          <span className="text-xs text-text-muted mr-1">Cycles:</span>
          <button
            onClick={() => onSelectCycle(null)}
            className={clsx(
              'px-3 py-1 text-xs rounded-md transition-colors',
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
                  'px-3 py-1 text-xs rounded-md transition-colors',
                  selectedCycle === cycle
                    ? 'bg-accent-cyan/20 text-accent-cyan'
                    : 'bg-bg-tertiary text-text-secondary hover:bg-bg-hover'
                )}
              >
                Cycle {cycle}
              </button>
            )
          )}
        </div>
      )}
    </div>
  );
}
