/**
 * PipelineStatusBadge — read-only pipeline execution status indicator.
 *
 * Replaces the ControlPanel with a pure monitoring badge that shows
 * whether the pipeline is running, stopped, paused, etc. The pipeline
 * is controlled via the CLI, not the UI.
 */

import { pipelineApi } from '@/api/client';
import { useAppStore } from '@/store/appStore';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
    AlertCircleIcon,
    CheckCircle2Icon,
    CircleDotIcon,
    Loader2Icon,
    PauseCircleIcon,
    SquareIcon,
} from 'lucide-react';

const STATUS_MAP: Record<
  string,
  {
    label: string;
    color: string;
    bg: string;
    border: string;
    icon: React.ElementType;
    pulse: boolean;
  }
> = {
  running: {
    label: 'Running',
    color: 'text-accent-cyan',
    bg: 'bg-accent-cyan/10',
    border: 'border-accent-cyan/40',
    icon: Loader2Icon,
    pulse: true,
  },
  success: {
    label: 'Complete',
    color: 'text-status-success',
    bg: 'bg-status-success/10',
    border: 'border-status-success/40',
    icon: CheckCircle2Icon,
    pulse: false,
  },
  error: {
    label: 'Error',
    color: 'text-status-error',
    bg: 'bg-status-error/10',
    border: 'border-status-error/40',
    icon: AlertCircleIcon,
    pulse: false,
  },
  paused: {
    label: 'Paused',
    color: 'text-status-warning',
    bg: 'bg-status-warning/10',
    border: 'border-status-warning/40',
    icon: PauseCircleIcon,
    pulse: false,
  },
  stopped: {
    label: 'Stopped',
    color: 'text-status-warning',
    bg: 'bg-status-warning/10',
    border: 'border-status-warning/40',
    icon: SquareIcon,
    pulse: false,
  },
  ready: {
    label: 'Ready',
    color: 'text-accent-cyan',
    bg: 'bg-accent-cyan/10',
    border: 'border-accent-cyan/40',
    icon: CircleDotIcon,
    pulse: false,
  },
  initialized: {
    label: 'Not Started',
    color: 'text-text-muted',
    bg: 'bg-bg-tertiary/50',
    border: 'border-border-subtle',
    icon: CircleDotIcon,
    pulse: false,
  },
  configuring: {
    label: 'Configuring',
    color: 'text-accent-purple',
    bg: 'bg-accent-purple/10',
    border: 'border-accent-purple/40',
    icon: Loader2Icon,
    pulse: true,
  },
};

export function PipelineStatusBadge() {
  const { activeProject } = useAppStore();

  // Poll the lock-file-based status endpoint for real-time accuracy
  const { data: runStatus } = useQuery({
    queryKey: ['pipeline-run-status', activeProject?.id],
    queryFn: () => pipelineApi.status(activeProject!.id).then((r) => r.data),
    enabled: !!activeProject?.id && !!activeProject?.is_setup,
    refetchInterval: 2000,
  });

  // Determine effective status
  const projectStatus = activeProject?.status ?? 'initialized';
  const isLiveRunning = runStatus?.running ?? false;

  // Lock-file says running → override project status
  const effectiveStatus = isLiveRunning ? 'running' : projectStatus;

  const config = STATUS_MAP[effectiveStatus] ?? STATUS_MAP.initialized;
  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${config.bg} ${config.border}`}
    >
      {/* Status dot / spinner */}
      {config.pulse ? (
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
          className="flex items-center"
        >
          <Icon className={`w-4 h-4 ${config.color}`} />
        </motion.div>
      ) : (
        <Icon className={`w-4 h-4 ${config.color}`} />
      )}

      {/* Label */}
      <span className={`text-sm font-medium ${config.color}`}>{config.label}</span>

      {/* Live dot for running */}
      {isLiveRunning && (
        <span className="relative flex h-2 w-2 ml-1">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-cyan opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-cyan" />
        </span>
      )}
    </motion.div>
  );
}
