import { projectsApi } from '@/api/client';
import { useAppStore } from '@/store/appStore';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import { XIcon } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export function LinkProjectModal() {
  const { modals, closeModal, setActiveProject } = useAppStore();
  const [projectPath, setProjectPath] = useState('');
  const [projectName, setProjectName] = useState('');
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const createMutation = useMutation({
    mutationFn: () =>
      projectsApi.create({
        project_path: projectPath,
        name: projectName || undefined,
      }),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setActiveProject(response.data);
      closeModal('linkProject');
      setProjectPath('');
      setProjectName('');
      navigate(`/dashboard/${response.data.id}`);
    },
  });

  if (!modals.linkProject) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        onClick={() => closeModal('linkProject')}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          onClick={(e) => e.stopPropagation()}
          className="bg-bg-secondary rounded-xl border border-border-subtle p-6 w-full max-w-md"
        >
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold">Link Project</h2>
            <button
              onClick={() => closeModal('linkProject')}
              className="p-1 hover:bg-bg-hover rounded"
            >
              <XIcon className="w-5 h-5" />
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">
                Project Path *
              </label>
              <input
                type="text"
                value={projectPath}
                onChange={(e) => setProjectPath(e.target.value)}
                placeholder="/path/to/your/project"
                className="input"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">
                Project Name
              </label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="Auto-detected from path"
                className="input"
              />
            </div>

            {createMutation.isError && (
              <p className="text-sm text-status-error">
                {(createMutation.error as any)?.response?.data?.error ||
                  'Failed to link project'}
              </p>
            )}

            <div className="flex space-x-3">
              <button
                onClick={() => createMutation.mutate()}
                disabled={!projectPath || createMutation.isPending}
                className="btn-primary flex-1"
              >
                {createMutation.isPending ? 'Linking...' : 'Link Project'}
              </button>
              <button
                onClick={() => closeModal('linkProject')}
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
