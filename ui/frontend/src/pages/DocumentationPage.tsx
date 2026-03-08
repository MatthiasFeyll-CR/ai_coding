import { ContextTab } from '@/components/docs/ContextTab';
import { ExecutionTab } from '@/components/docs/ExecutionTab';
import { OverviewTab } from '@/components/docs/OverviewTab';
import { SkillsTab } from '@/components/docs/SkillsTab';
import { TestingTab } from '@/components/docs/TestingTab';
import { WorkflowTab } from '@/components/docs/WorkflowTab';
import clsx from 'clsx';
import { motion } from 'framer-motion';
import {
    BookOpenIcon,
    BoxesIcon,
    BrainCircuitIcon,
    LayersIcon,
    ShieldCheckIcon,
    WorkflowIcon
} from 'lucide-react';
import { useState } from 'react';

const TABS = [
  { id: 'overview', label: 'Overview', icon: BookOpenIcon },
  { id: 'workflow', label: 'Workflow', icon: WorkflowIcon },
  { id: 'execution', label: 'Execution', icon: BoxesIcon },
  { id: 'context', label: 'Context', icon: LayersIcon },
  { id: 'testing', label: 'Testing', icon: ShieldCheckIcon },
  { id: 'skills', label: 'Skills', icon: BrainCircuitIcon },
] as const;

type TabId = (typeof TABS)[number]['id'];

export function DocumentationPage() {
  const [activeTab, setActiveTab] = useState<TabId>('overview');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-accent-purple/20">
          <BookOpenIcon className="w-6 h-6 text-accent-purple" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Documentation</h1>
          <p className="text-sm text-text-muted">
            How the Ralph Pipeline works — from specification to deployment
          </p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 p-1 bg-bg-secondary rounded-xl border border-border-subtle overflow-x-auto">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap',
                isActive
                  ? 'bg-accent-purple/20 text-accent-purple shadow-sm'
                  : 'text-text-muted hover:text-text-primary hover:bg-bg-tertiary'
              )}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <motion.div
        key={activeTab}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
      >
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'workflow' && <WorkflowTab />}
        {activeTab === 'execution' && <ExecutionTab />}
        {activeTab === 'context' && <ContextTab />}
        {activeTab === 'testing' && <TestingTab />}
        {activeTab === 'skills' && <SkillsTab />}
      </motion.div>
    </div>
  );
}
