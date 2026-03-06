import type { MilestoneInfo } from '@/types';
import clsx from 'clsx';
import { motion } from 'framer-motion';
import { CheckCircle2Icon, Loader2Icon, PauseCircleIcon } from 'lucide-react';
import { useCallback, useMemo } from 'react';
import ReactFlow, {
  type Edge,
  Handle,
  type Node,
  type NodeProps,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';

interface MilestoneFlowProps {
  milestones: MilestoneInfo[];
  selectedMilestoneId: number | null;
  pipelineStatus: string;
  onSelectMilestone: (id: number) => void;
}

/** Derive the visual status of a milestone */
function getMilestoneStatus(
  milestone: MilestoneInfo,
  pipelineStatus: string
): 'completed' | 'running' | 'paused' | 'pending' {
  if (milestone.completed_at) return 'completed';
  if (milestone.started_at && milestone.phase !== 'pending') {
    if (pipelineStatus === 'running') return 'running';
    return 'paused';
  }
  return 'pending';
}

interface MilestoneNodeData {
  label: string;
  status: 'completed' | 'running' | 'paused' | 'pending';
  selected: boolean;
  onSelect: () => void;
}

function MilestoneNode({ data }: NodeProps<MilestoneNodeData>) {
  const borderColor: Record<string, string> = {
    completed: 'border-status-success',
    running: 'border-accent-cyan',
    paused: 'border-text-muted',
    pending: 'border-border-subtle',
  };

  return (
    <div
      onClick={(e) => {
        e.stopPropagation();
        data.onSelect();
      }}
      className={clsx(
        'px-5 py-3 rounded-lg border-2 bg-bg-tertiary cursor-pointer transition-all min-w-[160px]',
        borderColor[data.status],
        data.selected ? 'opacity-100 shadow-lg ring-1 ring-accent-cyan/30' : 'opacity-60 hover:opacity-90'
      )}
    >
      <Handle type="target" position={Position.Top} className="!opacity-0 !w-0 !h-0" />
      <div className="flex items-center justify-center gap-3">
        <span className="font-medium text-sm">{data.label}</span>
        <MilestoneStatusIcon status={data.status} />
      </div>
      <Handle type="source" position={Position.Bottom} className="!opacity-0 !w-0 !h-0" />
    </div>
  );
}

function MilestoneStatusIcon({ status }: { status: string }) {
  if (status === 'completed') {
    return <CheckCircle2Icon className="w-4 h-4 text-status-success flex-shrink-0" />;
  }
  if (status === 'running') {
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

const nodeTypes = { milestone: MilestoneNode };

export function MilestoneFlow({
  milestones,
  selectedMilestoneId,
  pipelineStatus,
  onSelectMilestone,
}: MilestoneFlowProps) {
  const handleSelect = useCallback(
    (id: number) => onSelectMilestone(id),
    [onSelectMilestone]
  );

  const { nodes, edges } = useMemo(() => {
    const NODE_HEIGHT = 56;
    const NODE_GAP = 40;

    const nodes: Node<MilestoneNodeData>[] = milestones.map((m, index) => ({
      id: String(m.id),
      type: 'milestone',
      position: { x: 40, y: index * (NODE_HEIGHT + NODE_GAP) },
      data: {
        label: m.name,
        status: getMilestoneStatus(m, pipelineStatus),
        selected: m.id === selectedMilestoneId,
        onSelect: () => handleSelect(m.id),
      },
      draggable: false,
      selectable: false,
    }));

    const edges: Edge[] = milestones.slice(0, -1).map((m, index) => {
      const nextM = milestones[index + 1];
      const sourceStatus = getMilestoneStatus(m, pipelineStatus);
      return {
        id: `m${m.id}-m${nextM.id}`,
        source: String(m.id),
        target: String(nextM.id),
        animated: sourceStatus === 'running',
        style: {
          stroke:
            sourceStatus === 'completed'
              ? 'var(--color-status-success, #22c55e)'
              : 'var(--color-border-subtle, #374151)',
        },
      };
    });

    return { nodes, edges };
  }, [milestones, selectedMilestoneId, pipelineStatus, handleSelect]);

  return (
    <div className="h-full w-full rf-static">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.4 }}
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
  );
}
