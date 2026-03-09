import { pipelineApi, projectsApi } from '@/api/client';
import { SetupFlow } from '@/components/infrastructure/SetupFlow';
import { DeleteProjectModal } from '@/components/modals/DeleteProjectModal';
import { OverviewDashboard } from '@/components/pipeline/OverviewDashboard';
import { ParametersPanel } from '@/components/pipeline/ParametersPanel';
import { PipelineStateView } from '@/components/pipeline/PipelineStateView';
import { PipelineStatusBadge } from '@/components/pipeline/PipelineStatusBadge';
import { TestAnalytics } from '@/components/pipeline/TestAnalytics';
import { TokenDashboard } from '@/components/pipeline/TokenDashboard';
import { EmptyState } from '@/components/shared/EmptyState';
import { notify } from '@/lib/notify';
import { useAppStore } from '@/store/appStore';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ActivityIcon,
  BeakerIcon,
  DollarSignIcon,
  FolderOpenIcon,
  LayoutDashboardIcon,
  LinkIcon,
  LockIcon,
  SettingsIcon,
  SlidersHorizontalIcon,
  WrenchIcon,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

type TabId = 'overview' | 'state' | 'costs' | 'tests' | 'params' | 'setup';

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'overview', label: 'Overview', icon: <LayoutDashboardIcon className="w-4 h-4" /> },
  { id: 'state', label: 'Pipeline State', icon: <ActivityIcon className="w-4 h-4" /> },
  { id: 'costs', label: 'Cost Tracking', icon: <DollarSignIcon className="w-4 h-4" /> },
  { id: 'tests', label: 'Test Results', icon: <BeakerIcon className="w-4 h-4" /> },
  { id: 'params', label: 'Parameters', icon: <SlidersHorizontalIcon className="w-4 h-4" /> },
  { id: 'setup', label: 'Setup', icon: <WrenchIcon className="w-4 h-4" /> },
];

export function DashboardPage() {
  const { activeProject, setActiveProject } = useAppStore();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [tooltipTab, setTooltipTab] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [unlinkOpen, setUnlinkOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Unlink project mutation
  const unlinkMutation = useMutation({
    mutationFn: (id: number) => projectsApi.delete(id),
    onSuccess: (_data, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      notify('success', 'Project unlinked successfully');
      if (activeProject?.id === deletedId) {
        setActiveProject(null);
        navigate('/dashboard');
      }
    },
    onError: () => {
      notify('error', 'Failed to unlink project');
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

  const urlTab = searchParams.get('tab') as TabId | null;
  const activeTab: TabId = urlTab && TABS.some((t) => t.id === urlTab) ? urlTab : 'overview';

  const setActiveTab = (tab: TabId) => {
    setSearchParams({ tab }, { replace: true });
  };

  // If URL has a projectId but no activeProject (or different one), load it
  const { data: urlProject } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.get(Number(projectId)).then((res) => res.data),
    enabled: !!projectId && (!activeProject || activeProject.id !== Number(projectId)),
  });

  // Sync URL project → store
  useEffect(() => {
    if (urlProject && (!activeProject || activeProject.id !== urlProject.id)) {
      setActiveProject(urlProject);
    }
  }, [urlProject, activeProject, setActiveProject]);

  // Sync store → URL (when project changes via sidebar/modal, update URL)
  useEffect(() => {
    if (activeProject && (!projectId || Number(projectId) !== activeProject.id)) {
      navigate(`/dashboard/${activeProject.id}?tab=${activeTab}`, { replace: true });
    }
  }, [activeProject, projectId, navigate, activeTab]);

  // Auto-navigate to setup tab if project needs setup and no tab is specified
  useEffect(() => {
    if (activeProject && !activeProject.is_setup && !urlTab) {
      setSearchParams({ tab: 'setup' }, { replace: true });
    }
  }, [activeProject, urlTab, setSearchParams]);

  // Determine if non-setup tabs should be disabled
  const setupRequired = !!activeProject && !activeProject.is_setup;

  // Fetch enriched milestones (config + state)
  const { data: milestonesData } = useQuery({
    queryKey: ['milestones', activeProject?.id],
    queryFn: () => pipelineApi.getMilestones(activeProject!.id).then((res) => res.data),
    enabled: !!activeProject?.id && !!activeProject?.is_setup,
    refetchInterval: 2000,
  });

  const milestones = milestonesData?.milestones ?? [];
  const maxBugfixCycles = milestonesData?.max_bugfix_cycles ?? 3;

  if (!activeProject) {
    return (
      <EmptyState
        icon={FolderOpenIcon}
        title="No Project Selected"
        description="Select a project from the sidebar or link a new one to get started."
        actionLabel="View Projects"
        onAction={() => navigate('/dashboard')}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{activeProject.name}</h1>
          <p className="text-text-secondary text-sm mt-1">
            {activeProject.root_path}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <PipelineStatusBadge />

          {/* Settings dropdown */}
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setSettingsOpen((v) => !v)}
              className="p-2 border border-border-emphasis text-text-secondary rounded-lg hover:bg-bg-hover hover:text-text-primary transition-colors"
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
                      setUnlinkOpen(true);
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-status-error hover:bg-bg-hover transition-colors"
                  >
                    <LinkIcon className="w-4 h-4" />
                    Unlink project
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      <DeleteProjectModal
        open={unlinkOpen}
        projectName={activeProject?.name ?? ''}
        onConfirm={() => {
          if (activeProject) unlinkMutation.mutate(activeProject.id);
          setUnlinkOpen(false);
        }}
        onCancel={() => setUnlinkOpen(false)}
      />

      {/* Tabs */}
      <div className="border-b border-border-subtle">
        <div className="flex space-x-1">
          {TABS.map((tab) => {
            const isDisabled = setupRequired && tab.id !== 'setup';
            const isActive = activeTab === tab.id;

            return (
              <div
                key={tab.id}
                className="relative"
                onMouseEnter={() => isDisabled ? setTooltipTab(tab.id) : null}
                onMouseLeave={() => setTooltipTab(null)}
              >
                <button
                  onClick={() => {
                    if (isDisabled) {
                      setTooltipTab(tab.id);
                      return;
                    }
                    setActiveTab(tab.id);
                  }}
                  className={`flex items-center space-x-2 px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors ${
                    isActive
                      ? 'bg-bg-secondary text-accent-cyan border-b-2 border-accent-cyan'
                      : isDisabled
                      ? 'text-text-muted cursor-not-allowed opacity-50'
                      : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
                  }`}
                  disabled={isDisabled}
                >
                  {isDisabled && <LockIcon className="w-3 h-3" />}
                  {tab.icon}
                  <span>{tab.label}</span>
                </button>

                {/* Tooltip for disabled tabs */}
                {isDisabled && tooltipTab === tab.id && (
                  <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 z-50 w-56 px-3 py-2 bg-bg-secondary border border-border-subtle rounded-lg shadow-xl text-center">
                    <p className="text-xs text-text-secondary">
                      Complete all setup checks first before accessing this tab.
                    </p>
                    <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-bg-secondary border-l border-t border-border-subtle rotate-45" />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.18, ease: 'easeInOut' }}
          className="flex-1"
        >
        {activeTab === 'overview' && (
          <OverviewDashboard
            projectId={activeProject.id}
            milestones={milestones}
            pipelineStatus={activeProject.status}
          />
        )}

        {activeTab === 'state' && (
          <PipelineStateView
            projectId={activeProject.id}
            milestones={milestones}
            maxBugfixCycles={maxBugfixCycles}
            pipelineStatus={activeProject.status}
          />
        )}

        {activeTab === 'setup' && (
          <SetupFlow project={activeProject} onSetupComplete={() => setActiveTab('overview')} />
        )}

        {activeTab === 'costs' && (
          <TokenDashboard projectId={activeProject.id} />
        )}

        {activeTab === 'tests' && (
          <TestAnalytics projectId={activeProject.id} />
        )}

        {activeTab === 'params' && (
          <ParametersPanel projectId={activeProject.id} />
        )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
