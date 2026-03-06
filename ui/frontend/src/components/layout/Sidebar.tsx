import { projectsApi } from '@/api/client';
import { useAppStore } from '@/store/appStore';
import { useQuery } from '@tanstack/react-query';
import clsx from 'clsx';
import { formatDistanceToNow } from 'date-fns';
import { motion } from 'framer-motion';
import { AlertTriangleIcon, PlusIcon } from 'lucide-react';

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar, activeProject, setActiveProject, openModal } =
    useAppStore();
  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list().then((res) => res.data),
  });

  const sidebarVariants = {
    expanded: { width: 280 },
    collapsed: { width: 60 },
  };

  return (
    <motion.aside
      className="bg-bg-secondary border-r border-border-subtle flex flex-col"
      initial={false}
      animate={sidebarCollapsed ? 'collapsed' : 'expanded'}
      variants={sidebarVariants}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
    >
      {/* Header */}
      <div className="p-4 border-b border-border-subtle flex items-center justify-between">
        {!sidebarCollapsed && (
          <h2 className="text-lg font-semibold text-accent-cyan">Pipeline Executor</h2>
        )}
        <button
          onClick={toggleSidebar}
          className="p-2 hover:bg-bg-hover rounded-md transition-colors"
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {sidebarCollapsed ? '→' : '←'}
        </button>
      </div>

      {/* Projects List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {!sidebarCollapsed && (
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-text-secondary">Projects</h3>
            <button
              onClick={() => openModal('linkProject')}
              className="p-1 hover:bg-bg-hover rounded"
              title="Add Project"
            >
              <PlusIcon className="w-4 h-4" />
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="text-center text-text-muted">Loading...</div>
        ) : projects && projects.length > 0 ? (
          projects.map((project) => (
            <motion.button
              key={project.id}
              onClick={() => setActiveProject(project)}
              className={clsx(
                'w-full p-3 rounded-lg text-left transition-colors',
                'hover:bg-bg-tertiary',
                activeProject?.id === project.id &&
                  'bg-bg-tertiary border-l-4 border-accent-cyan'
              )}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {!sidebarCollapsed ? (
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{project.name}</span>
                    <StatusIcon status={project.status} />
                  </div>
                  {project.last_run_at && (
                    <span className="text-xs text-text-muted">
                      {formatDistanceToNow(new Date(project.last_run_at), {
                        addSuffix: true,
                      })}
                    </span>
                  )}
                </div>
              ) : (
                <StatusIcon status={project.status} />
              )}
            </motion.button>
          ))
        ) : (
          !sidebarCollapsed && (
            <div className="text-center text-text-muted text-sm">No projects yet</div>
          )
        )}
      </div>

      {/* Alerts Section */}
      <div className="border-t border-border-subtle p-4">
        {!sidebarCollapsed && (
          <div className="flex items-center space-x-2 text-status-warning">
            <AlertTriangleIcon className="w-5 h-5" />
            <span className="text-sm">System Alerts</span>
          </div>
        )}
      </div>
    </motion.aside>
  );
}

function StatusIcon({ status }: { status: string }) {
  const icons: Record<string, string> = {
    running: '⚡',
    success: '✓',
    error: '!',
    ready: '●',
    initialized: '○',
    paused: '⏸️',
    configuring: '⚙️',
  };

  const colors: Record<string, string> = {
    running: 'text-accent-cyan',
    success: 'text-status-success',
    error: 'text-status-error',
    ready: 'text-accent-cyan',
    initialized: 'text-text-muted',
    paused: 'text-status-warning',
    configuring: 'text-accent-purple',
  };

  return <span className={colors[status] || 'text-text-muted'}>{icons[status] || '○'}</span>;
}
