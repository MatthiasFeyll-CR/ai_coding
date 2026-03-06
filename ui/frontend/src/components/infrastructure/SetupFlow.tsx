import { projectsApi } from '@/api/client';
import { useWebSocket } from '@/hooks/useWebSocket';
import type { Project } from '@/types';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import {
    CheckCircleIcon,
    FileTextIcon,
    FolderIcon,
    LoaderIcon,
    PlayIcon,
    SettingsIcon,
    XCircleIcon,
} from 'lucide-react';
import { useEffect, useState } from 'react';

interface SetupFlowProps {
  project: Project;
}

interface ProgressEntry {
  step: string;
  status: string;
  message: string;
}

export function SetupFlow({ project }: SetupFlowProps) {
  const [configuring, setConfiguring] = useState(project.status === 'configuring');
  const [progress, setProgress] = useState<ProgressEntry[]>([]);
  const queryClient = useQueryClient();
  const { subscribe } = useWebSocket(project.id);

  // Fetch docs pre-check for this project
  const { data: preCheck } = useQuery({
    queryKey: ['preCheck', project.id],
    queryFn: () => projectsApi.preCheck(project.root_path),
    select: (res) => res.data,
  });

  // Listen for setup_progress WebSocket events
  useEffect(() => {
    const unsub = subscribe('setup_progress', (data) => {
      setProgress((prev) => [...prev, data]);
      if (data.status === 'complete' || data.status === 'error') {
        setConfiguring(false);
        // Refresh project data so is_setup re-evaluates
        queryClient.invalidateQueries({ queryKey: ['projects'] });
      }
    });
    return unsub;
  }, [subscribe, queryClient]);

  // Invoke configurator
  const configureMutation = useMutation({
    mutationFn: () => projectsApi.configure(project.id),
    onSuccess: () => {
      setConfiguring(true);
      setProgress([]);
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.error || 'Failed to start configurator';
      setProgress((prev) => [...prev, { step: 'error', status: 'error', message: msg }]);
    },
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{project.name}</h1>
          <p className="text-text-secondary text-sm mt-1">{project.root_path}</p>
        </div>
        <span className="px-3 py-1 rounded-full text-xs font-medium bg-yellow-500/20 text-yellow-400">
          Setup Required
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Docs Structure Panel */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-bg-secondary border border-border-subtle rounded-xl p-5"
        >
          <div className="flex items-center space-x-3 mb-4">
            <FolderIcon className="w-5 h-5 text-accent-cyan" />
            <h3 className="text-lg font-semibold">Docs Structure</h3>
          </div>

          {preCheck ? (
            <div className="space-y-2">
              {Object.entries(preCheck.docs_structure).map(([path, info]) => (
                <div
                  key={path}
                  className="flex items-center justify-between p-2.5 bg-bg-tertiary rounded-lg"
                >
                  <div className="flex items-center space-x-2">
                    <FileTextIcon className="w-4 h-4 text-text-muted" />
                    <span className="text-sm font-mono">{path}</span>
                  </div>
                  {info.exists ? (
                    <CheckCircleIcon className="w-4 h-4 text-status-success" />
                  ) : (
                    <XCircleIcon className="w-4 h-4 text-text-muted opacity-40" />
                  )}
                </div>
              ))}

              {/* Existing infrastructure files */}
              {preCheck.existing_infrastructure.length > 0 && (
                <div className="mt-4 pt-3 border-t border-border-subtle">
                  <p className="text-xs text-text-muted mb-2 uppercase tracking-wider">
                    Existing Infrastructure Files
                  </p>
                  {preCheck.existing_infrastructure.map((f) => (
                    <div
                      key={f.file}
                      className="flex items-center justify-between p-2 bg-bg-tertiary rounded-lg mb-1"
                    >
                      <span className="text-sm font-mono">{f.file}</span>
                      <span className="text-xs text-text-muted">
                        {(f.size / 1024).toFixed(1)} KB
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center py-8 text-text-muted">
              <LoaderIcon className="w-5 h-5 animate-spin mr-2" />
              Scanning project…
            </div>
          )}
        </motion.div>

        {/* Configurator Panel */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-bg-secondary border border-border-subtle rounded-xl p-5"
        >
          <div className="flex items-center space-x-3 mb-4">
            <SettingsIcon className="w-5 h-5 text-accent-purple" />
            <h3 className="text-lg font-semibold">Pipeline Configurator</h3>
          </div>

          <p className="text-sm text-text-secondary mb-4">
            Invoke the Pipeline Configurator skill to generate{' '}
            <span className="font-mono text-accent-cyan">pipeline-config.json</span>,
            test environment, and infrastructure files for this project.
          </p>

          {!configuring && progress.length === 0 && (
            <button
              onClick={() => configureMutation.mutate()}
              disabled={configureMutation.isPending}
              className="btn-primary w-full flex items-center justify-center space-x-2"
            >
              <PlayIcon className="w-4 h-4" />
              <span>
                {configureMutation.isPending
                  ? 'Starting…'
                  : 'Run Pipeline Configurator'}
              </span>
            </button>
          )}

          {/* Progress log */}
          <AnimatePresence>
            {(configuring || progress.length > 0) && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="mt-4 space-y-2"
              >
                {configuring && (
                  <div className="flex items-center space-x-2 text-accent-cyan text-sm">
                    <LoaderIcon className="w-4 h-4 animate-spin" />
                    <span>Configurator running…</span>
                  </div>
                )}

                <div className="max-h-64 overflow-y-auto space-y-1.5 bg-bg-tertiary rounded-lg p-3">
                  {progress.map((entry, i) => (
                    <div key={i} className="flex items-start space-x-2 text-sm">
                      {entry.status === 'error' ? (
                        <XCircleIcon className="w-4 h-4 text-status-error mt-0.5 shrink-0" />
                      ) : entry.status === 'complete' ? (
                        <CheckCircleIcon className="w-4 h-4 text-status-success mt-0.5 shrink-0" />
                      ) : (
                        <LoaderIcon className="w-4 h-4 text-text-muted mt-0.5 shrink-0 animate-spin" />
                      )}
                      <span className="text-text-secondary">{entry.message}</span>
                    </div>
                  ))}
                  {progress.length === 0 && configuring && (
                    <p className="text-text-muted text-xs">Waiting for progress updates…</p>
                  )}
                </div>

                {/* Done / retry */}
                {!configuring && progress.some((p) => p.status === 'complete') && (
                  <div className="text-center pt-2">
                    <CheckCircleIcon className="w-10 h-10 text-status-success mx-auto mb-2" />
                    <p className="font-semibold">Configuration Complete</p>
                    <p className="text-text-muted text-sm">
                      Refreshing project…
                    </p>
                  </div>
                )}

                {!configuring && progress.some((p) => p.status === 'error') && (
                  <button
                    onClick={() => {
                      setProgress([]);
                      configureMutation.mutate();
                    }}
                    className="btn-secondary w-full mt-2"
                  >
                    Retry
                  </button>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </div>
  );
}
