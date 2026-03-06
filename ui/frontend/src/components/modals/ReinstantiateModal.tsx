import { projectsApi } from '@/api/client';
import { useAppStore } from '@/store/appStore';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { AnimatePresence, motion } from 'framer-motion';
import { RotateCcwIcon, XIcon } from 'lucide-react';

export function ReinstantiateModal() {
  const { modals, closeModal, activeProject } = useAppStore();
  const queryClient = useQueryClient();

  const { data: snapshots, isLoading } = useQuery({
    queryKey: ['snapshots', activeProject?.id],
    queryFn: () =>
      projectsApi.listSnapshots(activeProject!.id).then((res) => res.data),
    enabled: !!activeProject?.id && modals.reinstantiate,
  });

  const restoreMutation = useMutation({
    mutationFn: (snapshotId: number) =>
      projectsApi.restoreSnapshot(activeProject!.id, snapshotId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-state'] });
      closeModal('reinstantiate');
    },
  });

  if (!modals.reinstantiate) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        onClick={() => closeModal('reinstantiate')}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          onClick={(e) => e.stopPropagation()}
          className="bg-bg-secondary rounded-xl border border-border-subtle p-6 w-full max-w-lg"
        >
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold">Reinstantiate Pipeline</h2>
            <button
              onClick={() => closeModal('reinstantiate')}
              className="p-1 hover:bg-bg-hover rounded"
            >
              <XIcon className="w-5 h-5" />
            </button>
          </div>

          <p className="text-text-secondary text-sm mb-4">
            Select a snapshot to restore the pipeline state to. This will overwrite
            the current state.
          </p>

          {isLoading ? (
            <p className="text-text-muted text-center py-4">Loading snapshots...</p>
          ) : snapshots && snapshots.length > 0 ? (
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {snapshots.map((snapshot) => (
                <div
                  key={snapshot.id}
                  className="flex items-center justify-between p-3 bg-bg-tertiary rounded-lg hover:bg-bg-hover transition-colors"
                >
                  <div>
                    <p className="font-medium">
                      {snapshot.phase || 'Full State'}{' '}
                      {snapshot.milestone_id
                        ? `(Milestone ${snapshot.milestone_id})`
                        : ''}
                    </p>
                    <p className="text-xs text-text-muted">
                      {snapshot.snapshot_type} &bull;{' '}
                      {formatDistanceToNow(new Date(snapshot.created_at), {
                        addSuffix: true,
                      })}
                    </p>
                  </div>
                  <button
                    onClick={() => restoreMutation.mutate(snapshot.id)}
                    disabled={restoreMutation.isPending}
                    className="flex items-center space-x-1 px-3 py-1.5 text-sm bg-accent-cyan/10 text-accent-cyan rounded hover:bg-accent-cyan/20 transition-colors"
                  >
                    <RotateCcwIcon className="w-4 h-4" />
                    <span>Restore</span>
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-text-muted text-center py-4">No snapshots available</p>
          )}

          <div className="mt-4 flex justify-end">
            <button
              onClick={() => closeModal('reinstantiate')}
              className="btn-secondary"
            >
              Close
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
