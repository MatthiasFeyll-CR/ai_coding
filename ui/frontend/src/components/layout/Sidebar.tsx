import { projectsApi } from '@/api/client';
import { useAppStore } from '@/store/appStore';
import { useQuery } from '@tanstack/react-query';
import clsx from 'clsx';
import { formatDistanceToNow } from 'date-fns';
import { motion } from 'framer-motion';
import { BookOpenIcon, PlusIcon, SettingsIcon } from 'lucide-react';
import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

const STATUS_CONFIG: Record<string, { color: string; label: string; description: string }> = {
  initialized: {
    color: 'bg-text-muted',
    label: 'Initialized',
    description: 'Project linked but not yet configured',
  },
  ready: {
    color: 'bg-accent-cyan',
    label: 'Ready',
    description: 'Configured and ready to run',
  },
  running: {
    color: 'bg-accent-cyan animate-pulse',
    label: 'Running',
    description: 'Pipeline is actively executing',
  },
  paused: {
    color: 'bg-status-warning',
    label: 'Paused',
    description: 'Execution paused — can be resumed',
  },
  error: {
    color: 'bg-status-error',
    label: 'Error',
    description: 'Pipeline stopped due to an error',
  },
  success: {
    color: 'bg-status-success',
    label: 'Complete',
    description: 'All milestones finished successfully',
  },
  configuring: {
    color: 'bg-accent-purple animate-pulse',
    label: 'Configuring',
    description: 'Pipeline configuration in progress',
  },
  stopped: {
    color: 'bg-status-warning',
    label: 'Stopped',
    description: 'Pipeline was stopped — can be resumed',
  },
};

function StatusIndicator({ status }: { status: string }) {
  const [showTooltip, setShowTooltip] = useState(false);
  const config = STATUS_CONFIG[status] ?? {
    color: 'bg-text-muted',
    label: status,
    description: 'Unknown state',
  };

  return (
    <div
      className="relative flex items-center"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <span
        className={clsx('w-2.5 h-2.5 rounded-full shrink-0', config.color)}
      />

      {showTooltip && (
        <div className="absolute left-full ml-2 z-50 w-48 px-3 py-2 bg-bg-secondary border border-border-subtle rounded-lg shadow-xl pointer-events-none">
          <p className="text-xs font-semibold text-text-primary">{config.label}</p>
          <p className="text-xs text-text-muted mt-0.5">{config.description}</p>
        </div>
      )}
    </div>
  );
}

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar, activeProject, setActiveProject, openModal } =
    useAppStore();
  const navigate = useNavigate();
  const location = useLocation();
  const isSettingsActive = location.pathname === '/settings';
  const isDocsActive = location.pathname === '/documentation';

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
      className="bg-bg-secondary/70 backdrop-blur-xl border-r border-white/[0.06] flex flex-col"
      initial={false}
      animate={sidebarCollapsed ? 'collapsed' : 'expanded'}
      variants={sidebarVariants}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
    >
      {/* Header */}
      <div className="p-4 border-b border-border-subtle flex items-center justify-between">
        {!sidebarCollapsed && (
          <Link to="/dashboard" className="text-lg font-semibold text-accent-cyan hover:text-accent-cyan/80 transition-colors">
            Pipeline Executor
          </Link>
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

        {sidebarCollapsed && (
          <div className="flex justify-center mb-2">
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
              onClick={() => {
                setActiveProject(project);
                navigate(`/dashboard/${project.id}`);
              }}
              className={clsx(
                'w-full rounded-lg text-left transition-colors',
                'hover:bg-bg-tertiary',
                sidebarCollapsed ? 'p-2 flex items-center justify-center' : 'p-3',
                activeProject?.id === project.id && !isSettingsActive && !isDocsActive &&
                  'bg-bg-tertiary border-l-4 border-accent-cyan'
              )}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {sidebarCollapsed ? (
                <StatusIndicator status={project.status} />
              ) : (
                <div className="flex items-center gap-3">
                  
                  <div className="min-w-0 flex-1">
                    <span className="font-medium truncate block">{project.name}</span>
                    {project.last_run_at && (
                      <span className="text-xs text-text-muted">
                        {formatDistanceToNow(new Date(project.last_run_at), {
                          addSuffix: true,
                        })}
                      </span>
                    )}
                  </div>
                  <StatusIndicator status={project.status} />
                </div>
              )}
            </motion.button>
          ))
        ) : (
          !sidebarCollapsed && (
            <div className="text-center text-text-muted text-sm">No projects yet</div>
          )
        )}
      </div>

      {/* Bottom nav: Documentation + Settings */}
      <div className="border-t border-border-subtle p-4 space-y-2">
        <button
          onClick={() => navigate('/documentation')}
          className={clsx(
            'w-full rounded-lg transition-colors',
            'hover:bg-bg-tertiary',
            sidebarCollapsed ? 'p-2 flex items-center justify-center' : 'p-3 flex items-center gap-3',
            isDocsActive && 'bg-bg-tertiary border-l-4 border-accent-purple'
          )}
        >
          <BookOpenIcon className="w-5 h-5 text-text-muted shrink-0" />
          {!sidebarCollapsed && (
            <span className="font-medium text-sm">Documentation</span>
          )}
        </button>
        <button
          onClick={() => navigate('/settings')}
          className={clsx(
            'w-full rounded-lg transition-colors',
            'hover:bg-bg-tertiary',
            sidebarCollapsed ? 'p-2 flex items-center justify-center' : 'p-3 flex items-center gap-3',
            isSettingsActive && 'bg-bg-tertiary border-l-4 border-accent-cyan'
          )}
        >
          <SettingsIcon className="w-5 h-5 text-text-muted shrink-0" />
          {!sidebarCollapsed && (
            <span className="font-medium text-sm">Settings</span>
          )}
        </button>
      </div>
    </motion.aside>
  );
}
