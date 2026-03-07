import { pipelineApi, projectsApi } from '@/api/client';
import { DeleteProjectModal } from '@/components/modals/DeleteProjectModal';
import { notify } from '@/lib/notify';
import { useAppStore } from '@/store/appStore';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import {
  HistoryIcon,
  PlayIcon,
  RotateCcwIcon,
  SettingsIcon,
  SquareIcon,
  Trash2Icon,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

export function ControlPanel() {
  const { activeProject, openModal, setActiveProject } = useAppStore();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

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

  const deleteMutation = useMutation({
    mutationFn: (id: number) => projectsApi.delete(id),
    onSuccess: (_data, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      notify('success', 'Project deleted successfully');
      if (activeProject?.id === deletedId) {
        setActiveProject(null);
        navigate('/');
      }
    },
    onError: () => {
      notify('error', 'Failed to delete project');
    },
  });

  // Close settings menu on outside click
  const handleClickOutside = useCallback((e: MouseEvent) => {
    if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
      setSettingsOpen(false);
    }
  }, []);

  useEffect(() => {
    if (settingsOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [settingsOpen, handleClickOutside]);

  const isRunning = activeProject?.status === 'running';
  const canResume =
    activeProject?.status === 'paused' ||
    activeProject?.status === 'error' ||
    activeProject?.status === 'stopped';
  const showStart = !isRunning && !canResume;

  return (
    <>
      <div className="flex items-center space-x-3">
        {isRunning ? (
          <button
            onClick={() => stopMutation.mutate()}
            disabled={stopMutation.isPending}
            className="flex items-center space-x-2 px-4 py-2 bg-status-error text-white rounded-lg hover:bg-status-error/90 disabled:opacity-50 transition-colors"
          >
            <SquareIcon className="w-5 h-5" />
            <span>Stop</span>
          </button>
        ) : canResume ? (
          <button
            onClick={() => resumeMutation.mutate()}
            disabled={resumeMutation.isPending}
            className="flex items-center space-x-2 px-4 py-2 bg-accent-cyan text-white rounded-lg hover:bg-accent-cyan/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <RotateCcwIcon className="w-5 h-5" />
            <span>Resume Pipeline</span>
          </button>
        ) : (
          <button
            onClick={() => startMutation.mutate()}
            disabled={!activeProject || startMutation.isPending}
            className="flex items-center space-x-2 px-4 py-2 bg-accent-cyan text-white rounded-lg hover:bg-accent-cyan/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <PlayIcon className="w-5 h-5" />
            <span>Start Pipeline</span>
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

        {/* Settings dropdown */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setSettingsOpen((v) => !v)}
            disabled={!activeProject}
            className="p-2 border border-border-emphasis text-text-secondary rounded-lg hover:bg-bg-hover hover:text-text-primary disabled:opacity-50 transition-colors"
            aria-label="Project settings"
          >
            <SettingsIcon className="w-5 h-5" />
          </button>

          <AnimatePresence>
            {settingsOpen && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: -4 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: -4 }}
                transition={{ duration: 0.12 }}
                className="absolute right-0 mt-2 z-50 w-48 py-1 bg-bg-secondary border border-border-subtle rounded-lg shadow-xl"
              >
                <button
                  onClick={() => {
                    setSettingsOpen(false);
                    setDeleteOpen(true);
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-status-error hover:bg-bg-hover transition-colors"
                >
                  <Trash2Icon className="w-4 h-4" />
                  Delete project
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      <DeleteProjectModal
        open={deleteOpen}
        projectName={activeProject?.name ?? ''}
        onConfirm={() => {
          if (activeProject) deleteMutation.mutate(activeProject.id);
          setDeleteOpen(false);
        }}
        onCancel={() => setDeleteOpen(false)}
      />
    </>
  );
}
