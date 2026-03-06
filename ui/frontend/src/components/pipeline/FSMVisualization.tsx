import type { PipelineState } from '@/types';
import { motion } from 'framer-motion';
import { useMemo } from 'react';
import ReactFlow, {
    Background,
    Controls,
    Edge,
    MiniMap,
    Node,
} from 'reactflow';
import 'reactflow/dist/style.css';

interface FSMVisualizationProps {
  state: PipelineState | undefined;
}

const phases = [
  { id: 'prd_generation', label: 'PRD Gen' },
  { id: 'ralph_execution', label: 'Ralph Exec' },
  { id: 'qa_review', label: 'QA Review' },
  { id: 'merge_verify', label: 'Merge Verify' },
  { id: 'reconciliation', label: 'Reconcile' },
];

function PhaseNode({ data }: { data: { label: string; status: string } }) {
  const statusColors: Record<string, string> = {
    pending: 'border-text-muted bg-bg-tertiary',
    active: 'border-accent-cyan bg-bg-tertiary shadow-glow-cyan',
    complete: 'border-status-success bg-bg-tertiary',
    error: 'border-status-error bg-bg-tertiary shadow-glow-error',
  };

  return (
    <motion.div
      className={`px-6 py-4 rounded-lg border-2 ${
        statusColors[data.status] || statusColors.pending
      }`}
      animate={
        data.status === 'active'
          ? { scale: [1, 1.05, 1], transition: { duration: 2, repeat: Infinity } }
          : {}
      }
    >
      <div className="text-center font-medium">{data.label}</div>
    </motion.div>
  );
}

const nodeTypes = { custom: PhaseNode };

export function FSMVisualization({ state }: FSMVisualizationProps) {
  const { nodes, edges } = useMemo(() => {
    const currentPhase = state?.milestones?.[state.current_milestone]?.phase;

    const nodes: Node[] = phases.map((phase, index) => {
      const status = currentPhase === phase.id ? 'active' : 'pending';

      return {
        id: phase.id,
        type: 'custom',
        position: { x: index * 200, y: 100 },
        data: {
          label: phase.label,
          status,
        },
      };
    });

    const edges: Edge[] = phases.slice(0, -1).map((phase, index) => ({
      id: `${phase.id}-${phases[index + 1].id}`,
      source: phase.id,
      target: phases[index + 1].id,
      animated: currentPhase === phase.id,
    }));

    return { nodes, edges };
  }, [state]);

  return (
    <div className="bg-bg-secondary rounded-lg p-6 h-96">
      <h2 className="text-lg font-semibold mb-4">Pipeline Status</h2>
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView>
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
