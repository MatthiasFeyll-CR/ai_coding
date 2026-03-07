import { pipelineApi, projectsApi } from '@/api/client';
import { SetupFlow } from '@/components/infrastructure/SetupFlow';
import { ControlPanel } from '@/components/pipeline/ControlPanel';
import { MilestoneDetail } from '@/components/pipeline/MilestoneDetail';
import { MilestoneFlow } from '@/components/pipeline/MilestoneFlow';
import { TokenDashboard } from '@/components/pipeline/TokenDashboard';
import { Badge } from '@/components/shared/Badge';
import { Card } from '@/components/shared/Card';
import { EmptyState } from '@/components/shared/EmptyState';
import { useAppStore } from '@/store/appStore';
import { useQuery } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ActivityIcon,
  BeakerIcon,
  DollarSignIcon,
  FolderOpenIcon,
  GitBranchIcon,
  LockIcon,
  WrenchIcon,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

type TabId = 'setup' | 'state' | 'git' | 'costs' | 'tests';

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'setup', label: 'Setup', icon: <WrenchIcon className="w-4 h-4" /> },
  { id: 'state', label: 'Pipeline State', icon: <ActivityIcon className="w-4 h-4" /> },
  { id: 'git', label: 'Git Operations', icon: <GitBranchIcon className="w-4 h-4" /> },
  { id: 'costs', label: 'Cost Tracking', icon: <DollarSignIcon className="w-4 h-4" /> },
  { id: 'tests', label: 'Test Results', icon: <BeakerIcon className="w-4 h-4" /> },
];

export function DashboardPage() {
  const { activeProject, setActiveProject } = useAppStore();
  const [searchParams, setSearchParams] = useSearchParams();
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [tooltipTab, setTooltipTab] = useState<string | null>(null);

  // Read active tab from URL, default to 'state'
  const urlTab = searchParams.get('tab') as TabId | null;
  const activeTab: TabId = urlTab && TABS.some((t) => t.id === urlTab) ? urlTab : 'state';

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

  // Fetch pipeline state (only poll when project is fully set up)
  const { data: pipelineState } = useQuery({
    queryKey: ['project-state', activeProject?.id],
    queryFn: () => projectsApi.getState(activeProject!.id).then((res) => res.data),
    enabled: !!activeProject?.id && !!activeProject?.is_setup,
    refetchInterval: 5000,
  });

  // Fetch enriched milestones (config + state)
  const { data: milestonesData } = useQuery({
    queryKey: ['milestones', activeProject?.id],
    queryFn: () => pipelineApi.getMilestones(activeProject!.id).then((res) => res.data),
    enabled: !!activeProject?.id && !!activeProject?.is_setup,
    refetchInterval: 5000,
  });

  const milestones = milestonesData?.milestones ?? [];
  const maxBugfixCycles = milestonesData?.max_bugfix_cycles ?? 3;

  const [selectedMilestoneId, setSelectedMilestoneId] = useState<number | null>(null);

  // Auto-select the next milestone to process (or the current running one)
  const effectiveMilestoneId = useMemo(() => {
    if (selectedMilestoneId !== null) return selectedMilestoneId;
    if (milestones.length === 0) return null;

    // Find the running milestone or the first non-completed one
    const running = milestones.find(
      (m) => m.started_at && !m.completed_at && m.phase !== 'pending'
    );
    if (running) return running.id;

    const nextPending = milestones.find((m) => !m.completed_at);
    if (nextPending) return nextPending.id;

    // All complete — show the last one
    return milestones[milestones.length - 1].id;
  }, [selectedMilestoneId, milestones]);

  const selectedMilestone = milestones.find((m) => m.id === effectiveMilestoneId) ?? null;

  if (!activeProject) {
    return (
      <EmptyState
        icon={FolderOpenIcon}
        title="No Project Selected"
        description="Select a project from the sidebar or link a new one to get started."
        actionLabel="Link Project"
        onAction={() => useAppStore.getState().openModal('linkProject')}
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
        <ControlPanel />
      </div>

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
        {activeTab === 'setup' && (
          <SetupFlow project={activeProject} onSetupComplete={() => setActiveTab('state')} />
        )}

        {activeTab === 'state' && (
          <div className="flex gap-0 h-[calc(100vh-220px)] rounded-xl border border-white/[0.06] overflow-hidden">
            {/* Left panel — Milestone Flow (30%) */}
            <div className="w-[30%] border-r border-white/[0.06] flex flex-col bg-bg-secondary/50 backdrop-blur-xl">
              <div className="section-header">
                <ActivityIcon className="w-4 h-4 text-accent-green" />
                <h3>Milestones</h3>
              </div>
              <div className="flex-1">
                <MilestoneFlow
                  milestones={milestones}
                  selectedMilestoneId={effectiveMilestoneId}
                  pipelineStatus={activeProject.status}
                  onSelectMilestone={setSelectedMilestoneId}
                />
              </div>
            </div>

            {/* Right panel — Milestone Detail (70%) */}
            <div className="w-[70%] flex flex-col bg-bg-secondary/30 backdrop-blur-xl">
              {selectedMilestone ? (
                <MilestoneDetail
                  projectId={activeProject.id}
                  milestone={selectedMilestone}
                  maxBugfixCycles={maxBugfixCycles}
                  pipelineStatus={activeProject.status}
                />
              ) : (
                <div className="flex items-center justify-center h-full text-text-muted">
                  <p>Select a milestone to view details</p>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'git' && (
          <Card title="Git Operations">
            <div className="space-y-4">
              <div className="flex items-center space-x-3">
                <GitBranchIcon className="w-5 h-5 text-accent-cyan" />
                <div>
                  <p className="font-medium">
                    Branch: {pipelineState?.git_branch || 'main'}
                  </p>
                  <p className="text-sm text-text-secondary">
                    Git operations are managed automatically by the pipeline
                  </p>
                </div>
              </div>

              <div className="bg-bg-tertiary rounded-lg p-4">
                <h4 className="text-sm font-medium mb-2">Recent Operations</h4>
                {pipelineState?.git_log?.length ? (
                  <div className="space-y-2">
                    {pipelineState.git_log.map((entry, i) => (
                      <p key={i} className="text-sm font-mono text-text-secondary">
                        {entry}
                      </p>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-text-muted">No git operations yet</p>
                )}
              </div>
            </div>
          </Card>
        )}

        {activeTab === 'costs' && (
          <TokenDashboard projectId={activeProject.id} />
        )}

        {activeTab === 'tests' && (
          <Card title="Test Results">
            <div className="space-y-4">
              {pipelineState?.test_results?.length ? (
                pipelineState.test_results.map((result, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-3 bg-bg-tertiary rounded-lg"
                  >
                    <div>
                      <p className="font-medium">{result.name}</p>
                      <p className="text-xs text-text-muted">
                        {result.duration}s &bull; {result.milestone}
                      </p>
                    </div>
                    <Badge
                      variant={result.passed ? 'success' : 'error'}
                    >
                      {result.passed ? 'Passed' : 'Failed'}
                    </Badge>
                  </div>
                ))
              ) : (
                <EmptyState
                  icon={BeakerIcon}
                  title="No Test Results"
                  description="Test results will appear here after QA phases complete."
                />
              )}
            </div>
          </Card>
        )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
