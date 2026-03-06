import { pipelineApi } from '@/api/client';
import { useAppStore } from '@/store/appStore';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { HistoryIcon, PlayIcon, RotateCcwIcon, SquareIcon } from 'lucide-react';

export function ControlPanel() {
  const { activeProject, openModal } = useAppStore();
  const queryClient = useQueryClient();

  const startMutation = useMutation({
    mutationFn: () => pipelineApi.start(activeProject!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-state'] });
    },
  });

  const stopMutation = useMutation({
    mutationFn: () => pipelineApi.stop(activeProject!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-state'] });
    },
  });

  const resumeMutation = useMutation({
    mutationFn: () => pipelineApi.resume(activeProject!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-state'] });
    },
  });

  const isRunning = activeProject?.status === 'running';
  const canResume = activeProject?.status === 'paused' || activeProject?.status === 'error';

  return (
    <div className="flex items-center space-x-3">
      {!isRunning ? (
        <button
          onClick={() => startMutation.mutate()}
          disabled={!activeProject || startMutation.isPending}
          className="flex items-center space-x-2 px-4 py-2 bg-accent-cyan text-white rounded-lg hover:bg-accent-cyan/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <PlayIcon className="w-5 h-5" />
          <span>Start Pipeline</span>
        </button>
      ) : (
        <button
          onClick={() => stopMutation.mutate()}
          disabled={stopMutation.isPending}
          className="flex items-center space-x-2 px-4 py-2 bg-status-error text-white rounded-lg hover:bg-status-error/90 disabled:opacity-50 transition-colors"
        >
          <SquareIcon className="w-5 h-5" />
          <span>Stop</span>
        </button>
      )}

      {canResume && (
        <button
          onClick={() => resumeMutation.mutate()}
          disabled={resumeMutation.isPending}
          className="flex items-center space-x-2 px-4 py-2 border border-accent-cyan text-accent-cyan rounded-lg hover:bg-accent-cyan/10 disabled:opacity-50 transition-colors"
        >
          <RotateCcwIcon className="w-5 h-5" />
          <span>Resume</span>
        </button>
      )}

      <button
        onClick={() => openModal('reinstantiate')}
        disabled={!activeProject}
        className="flex items-center space-x-2 px-4 py-2 border border-border-emphasis text-text-primary rounded-lg hover:bg-bg-hover disabled:opacity-50 transition-colors"
      >
        <HistoryIcon className="w-5 h-5" />
        <span>Reinstantiate</span>
      </button>
    </div>
  );
}
