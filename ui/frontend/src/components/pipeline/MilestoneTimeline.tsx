import type { MilestoneInfo } from '@/types';
import clsx from 'clsx';
import { motion } from 'framer-motion';
import {
    CheckCircle2Icon,
    CircleDotIcon,
    CircleIcon,
    Loader2Icon,
    PauseCircleIcon,
    XCircleIcon,
} from 'lucide-react';

interface MilestoneTimelineProps {
  milestones: MilestoneInfo[];
  selectedMilestoneId: number | null;
  pipelineStatus: string;
  onSelectMilestone: (id: number) => void;
}

type MilestoneStatus = 'completed' | 'running' | 'paused' | 'failed' | 'pending';

function getMilestoneStatus(
  milestone: MilestoneInfo,
  pipelineStatus: string
): MilestoneStatus {
  if (milestone.completed_at) return 'completed';
  if (milestone.phase === 'failed') return 'failed';
  if (milestone.started_at && milestone.phase !== 'pending') {
    return pipelineStatus === 'running' ? 'running' : 'paused';
  }
  return 'pending';
}

const STATUS_CONFIG: Record<
  MilestoneStatus,
  { icon: typeof CheckCircle2Icon; color: string; rail: string; glow: string }
> = {
  completed: {
    icon: CheckCircle2Icon,
    color: 'text-status-success',
    rail: 'bg-status-success',
    glow: '',
  },
  running: {
    icon: Loader2Icon,
    color: 'text-accent-cyan',
    rail: 'bg-accent-cyan',
    glow: 'shadow-glow-cyan',
  },
  paused: {
    icon: PauseCircleIcon,
    color: 'text-text-muted',
    rail: 'bg-text-muted',
    glow: '',
  },
  failed: {
    icon: XCircleIcon,
    color: 'text-status-error',
    rail: 'bg-status-error',
    glow: 'shadow-glow-error',
  },
  pending: {
    icon: CircleIcon,
    color: 'text-border-emphasis',
    rail: 'bg-border-subtle',
    glow: '',
  },
};

export function MilestoneTimeline({
  milestones,
  selectedMilestoneId,
  pipelineStatus,
  onSelectMilestone,
}: MilestoneTimelineProps) {
  return (
    <div className="flex flex-col py-3 px-4 h-full overflow-y-auto">
      {milestones.map((milestone, index) => {
        const status = getMilestoneStatus(milestone, pipelineStatus);
        const config = STATUS_CONFIG[status];
        const isSelected = milestone.id === selectedMilestoneId;
        const isLast = index === milestones.length - 1;
        const Icon = config.icon;

        return (
          <div key={milestone.id} className="flex gap-3 group">
            {/* Rail */}
            <div className="flex flex-col items-center shrink-0 w-6">
              <motion.div
                className={clsx(
                  'relative z-10 flex items-center justify-center w-6 h-6 rounded-full',
                  isSelected && 'ring-2 ring-accent-cyan/40'
                )}
                animate={
                  status === 'running'
                    ? { scale: [1, 1.15, 1], transition: { duration: 2, repeat: Infinity } }
                    : {}
                }
              >
                {status === 'running' ? (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
                  >
                    <Icon className={clsx('w-5 h-5', config.color)} />
                  </motion.div>
                ) : status === 'pending' ? (
                  <CircleDotIcon className={clsx('w-5 h-5', config.color)} />
                ) : (
                  <Icon className={clsx('w-5 h-5', config.color)} />
                )}
              </motion.div>
              {!isLast && (
                <div
                  className={clsx(
                    'w-0.5 flex-1 min-h-[24px] transition-colors duration-300',
                    status === 'completed' ? config.rail : 'bg-border-subtle'
                  )}
                />
              )}
            </div>

            {/* Card */}
            <button
              onClick={() => onSelectMilestone(milestone.id)}
              className={clsx(
                'flex-1 text-left rounded-lg px-3 py-2.5 mb-2 transition-all duration-200 border',
                isSelected
                  ? 'bg-accent-cyan/[0.08] border-accent-cyan/40 shadow-[0_0_12px_rgba(6,182,212,0.12)]'
                  : 'bg-transparent border-transparent hover:bg-bg-tertiary/60 hover:border-border-subtle'
              )}
            >
              <div className="flex items-center justify-between">
                <span
                  className={clsx(
                    'font-medium text-sm truncate',
                    isSelected ? 'text-accent-cyan' : 'text-text-primary'
                  )}
                >
                  {milestone.name}
                </span>
                {milestone.bugfix_cycle > 0 && (
                  <span className="text-[10px] text-status-warning font-mono ml-2 shrink-0">
                    fix×{milestone.bugfix_cycle}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[11px] text-text-muted font-mono">{milestone.phase}</span>
                {milestone.stories > 0 && (
                  <span className="text-[10px] text-text-muted">
                    · {milestone.stories} stories
                  </span>
                )}
              </div>
            </button>
          </div>
        );
      })}
    </div>
  );
}
