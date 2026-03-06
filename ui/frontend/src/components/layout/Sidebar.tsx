import { projectsApi } from '@/api/client';
import { useAppStore } from '@/store/appStore';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import clsx from 'clsx';
import { formatDistanceToNow } from 'date-fns';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangleIcon, MoreVerticalIcon, PlusIcon, Trash2Icon } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar, activeProject, setActiveProject, openModal } =
    useAppStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [menuOpenId, setMenuOpenId] = useState<number | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list().then((res) => res.data),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => projectsApi.delete(id),
    onSuccess: (_data, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      if (activeProject?.id === deletedId) {
        setActiveProject(null);
        navigate('/');
      }
    },
  });

  // Close menu when clicking outside
  const handleClickOutside = useCallback(
    (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenId(null);
      }
    },
    []
  );

  useEffect(() => {
    if (menuOpenId !== null) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [menuOpenId, handleClickOutside]);

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
            <div key={project.id} className="relative group">
              <motion.button
                onClick={() => {
                  setActiveProject(project);
                  navigate(`/dashboard/${project.id}`);
                }}
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
                      <span className="font-medium truncate pr-6">{project.name}</span>
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

              {/* Three-dot menu */}
              {!sidebarCollapsed && (
                <div className="absolute right-2 top-3" ref={menuOpenId === project.id ? menuRef : undefined}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setMenuOpenId(menuOpenId === project.id ? null : project.id);
                    }}
                    className={clsx(
                      'p-1 rounded transition-colors',
                      'opacity-0 group-hover:opacity-100 focus:opacity-100',
                      'hover:bg-bg-hover text-text-muted hover:text-text-primary',
                      menuOpenId === project.id && 'opacity-100 bg-bg-hover text-text-primary'
                    )}
                    aria-label={`Project options for ${project.name}`}
                  >
                    <MoreVerticalIcon className="w-4 h-4" />
                  </button>

                  <AnimatePresence>
                    {menuOpenId === project.id && (
                      <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: -4 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: -4 }}
                        transition={{ duration: 0.12 }}
                        className="absolute right-0 mt-1 z-50 w-40 py-1 bg-bg-secondary border border-border-subtle rounded-lg shadow-lg"
                      >
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (window.confirm(`Delete "${project.name}"? This only removes it from the dashboard — project files are not affected.`)) {
                              deleteMutation.mutate(project.id);
                            }
                            setMenuOpenId(null);
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
              )}
            </div>
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
