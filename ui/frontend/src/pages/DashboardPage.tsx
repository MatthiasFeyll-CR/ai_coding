import { projectsApi } from '@/api/client';
import { InfrastructureTab } from '@/components/infrastructure/InfrastructureTab';
import { SetupFlow } from '@/components/infrastructure/SetupFlow';
import { ControlPanel } from '@/components/pipeline/ControlPanel';
import { FSMVisualization } from '@/components/pipeline/FSMVisualization';
import { LiveLogs } from '@/components/pipeline/LiveLogs';
import { MilestoneList } from '@/components/pipeline/MilestoneList';
import { TokenDashboard } from '@/components/pipeline/TokenDashboard';
import { Badge } from '@/components/shared/Badge';
import { Card } from '@/components/shared/Card';
import { EmptyState } from '@/components/shared/EmptyState';
import { useAppStore } from '@/store/appStore';
import { useQuery } from '@tanstack/react-query';
import {
    ActivityIcon,
    BeakerIcon,
    DollarSignIcon,
    FolderOpenIcon,
    GitBranchIcon,
    SettingsIcon,
} from 'lucide-react';
import { useState } from 'react';

type TabId = 'state' | 'git' | 'costs' | 'tests' | 'infrastructure';

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'state', label: 'Pipeline State', icon: <ActivityIcon className="w-4 h-4" /> },
  { id: 'git', label: 'Git Operations', icon: <GitBranchIcon className="w-4 h-4" /> },
  { id: 'costs', label: 'Cost Tracking', icon: <DollarSignIcon className="w-4 h-4" /> },
  { id: 'tests', label: 'Test Results', icon: <BeakerIcon className="w-4 h-4" /> },
  { id: 'infrastructure', label: 'Infrastructure', icon: <SettingsIcon className="w-4 h-4" /> },
];

export function DashboardPage() {
  const { activeProject } = useAppStore();
  const [activeTab, setActiveTab] = useState<TabId>('state');

  // Fetch pipeline state
  const { data: pipelineState } = useQuery({
    queryKey: ['project-state', activeProject?.id],
    queryFn: () => projectsApi.getState(activeProject!.id).then((res) => res.data),
    enabled: !!activeProject?.id,
    refetchInterval: 5000,
  });

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

  // Check if project needs setup
  if (!activeProject.is_setup) {
    return <SetupFlow project={activeProject} />;
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

      {/* FSM Visualization */}
      <Card title="Pipeline Progress">
        <FSMVisualization state={pipelineState} />
      </Card>

      {/* Tabs */}
      <div className="border-b border-border-subtle">
        <div className="flex space-x-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2 px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors ${
                activeTab === tab.id
                  ? 'bg-bg-secondary text-accent-cyan border-b-2 border-accent-cyan'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
              }`}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'state' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="space-y-6">
              <Card title="Milestones">
                <MilestoneList projectId={activeProject.id} />
              </Card>

              <Card title="Current State">
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-text-secondary">Status</span>
                    <Badge
                      variant={
                        pipelineState?.status === 'running'
                          ? 'info'
                          : pipelineState?.status === 'completed'
                          ? 'success'
                          : pipelineState?.status === 'failed'
                          ? 'error'
                          : 'default'
                      }
                    >
                      {pipelineState?.status || 'idle'}
                    </Badge>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-text-secondary">Phase</span>
                    <span className="font-mono text-sm">
                      {pipelineState?.current_phase || 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-text-secondary">Milestone</span>
                    <span className="font-mono text-sm">
                      {pipelineState?.current_milestone || 'N/A'}
                    </span>
                  </div>
                </div>
              </Card>
            </div>

            <Card title="Live Logs">
              <LiveLogs projectId={activeProject.id} />
            </Card>
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

        {activeTab === 'infrastructure' && (
          <InfrastructureTab projectId={activeProject.id} />
        )}
      </div>
    </div>
  );
}
