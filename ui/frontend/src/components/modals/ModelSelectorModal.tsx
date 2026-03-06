import { modelsApi, projectsApi } from '@/api/client';
import { useAppStore } from '@/store/appStore';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import { XIcon } from 'lucide-react';
import { useState } from 'react';

const PHASES = ['prd', 'ralph', 'qa', 'reconciliation'];

export function ModelSelectorModal() {
  const { modals, closeModal, activeProject } = useAppStore();
  const [models, setModels] = useState<Record<string, string>>({});
  const queryClient = useQueryClient();

  const { data: availableModels } = useQuery({
    queryKey: ['available-models'],
    queryFn: () => modelsApi.listAvailable().then((res) => res.data),
  });

  const { data: currentModels } = useQuery({
    queryKey: ['project-models', activeProject?.id],
    queryFn: () =>
      projectsApi.getModels(activeProject!.id).then((res) => {
        setModels(res.data);
        return res.data;
      }),
    enabled: !!activeProject?.id && modals.modelSelector,
  });

  const updateMutation = useMutation({
    mutationFn: () => projectsApi.updateModels(activeProject!.id, models),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-models'] });
      closeModal('modelSelector');
    },
  });

  if (!modals.modelSelector) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        onClick={() => closeModal('modelSelector')}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          onClick={(e) => e.stopPropagation()}
          className="bg-bg-secondary rounded-xl border border-border-subtle p-6 w-full max-w-md"
        >
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold">Model Configuration</h2>
            <button
              onClick={() => closeModal('modelSelector')}
              className="p-1 hover:bg-bg-hover rounded"
            >
              <XIcon className="w-5 h-5" />
            </button>
          </div>

          <div className="space-y-4">
            {PHASES.map((phase) => (
              <div key={phase}>
                <label className="block text-sm font-medium text-text-secondary mb-1 capitalize">
                  {phase} Phase
                </label>
                <select
                  value={models[phase] || ''}
                  onChange={(e) =>
                    setModels((prev) => ({ ...prev, [phase]: e.target.value }))
                  }
                  className="input"
                >
                  <option value="">Default</option>
                  {availableModels?.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </div>
            ))}

            <div className="flex space-x-3 pt-2">
              <button
                onClick={() => updateMutation.mutate()}
                disabled={updateMutation.isPending}
                className="btn-primary flex-1"
              >
                {updateMutation.isPending ? 'Saving...' : 'Save'}
              </button>
              <button
                onClick={() => closeModal('modelSelector')}
                className="btn-secondary flex-1"
              >
                Cancel
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
