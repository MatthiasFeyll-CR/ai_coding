# Ralph Pipeline UI - AI Agent Implementation Guide (Part 2)

## Continuation from Part 1

This document continues the implementation guide with React components, testing, and deployment instructions.

---

## 4. Frontend Implementation (Continued)

### 4.6 Main Application Component

**File: `ui/frontend/src/App.tsx`**

```typescript
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import {QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RequirementsPage } from '@/pages/RequirementsPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { Layout } from '@/components/layout/Layout';
import { useAppStore } from '@/store/appStore';
import { useEffect } from 'react';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  const { theme } = useAppStore();

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/requirements" element={<RequirementsPage />} />
          <Route path="/" element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="project/:projectId" element={<DashboardPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
```

### 4.7 Layout Components

**File: `ui/frontend/src/components/layout/Layout.tsx`**

```typescript
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export function Layout() {
  return (
    <div className="flex h-screen bg-bg-primary text-text-primary">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

**File: `ui/frontend/src/components/layout/Sidebar.tsx`**

```typescript
import { motion } from 'framer-motion';
import { FolderIcon, PlusIcon, AlertTriangleIcon } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { projectsApi } from '@/api/client';
import { useAppStore } from '@/store/appStore';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar, activeProject, setActiveProject, openModal } = useAppStore();
  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list().then(res => res.data),
  });

  const sidebarVariants = {
    expanded: { width: 280 },
    collapsed: { width: 60 }
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
          <h2 className="text-lg font-semibold text-accent-cyan">
            Pipeline Executor
          </h2>
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
                activeProject?.id === project.id && 'bg-bg-tertiary border-l-4 border-accent-cyan'
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
                      {formatDistanceToNow(new Date(project.last_run_at), { addSuffix: true })}
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
            <div className="text-center text-text-muted text-sm">
              No projects yet
            </div>
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
  const icons = {
    running: '⚡',
    success: '✓',
    error: '!',
    ready: '●',
    initialized: '○',
    paused: '⏸️',
  };

  const colors = {
    running: 'text-accent-cyan',
    success: 'text-status-success',
    error: 'text-status-error',
    ready: 'text-accent-cyan',
    initialized: 'text-text-muted',
    paused: 'text-status-warning',
  };

  return (
    <span className={colors[status as keyof typeof colors]}>
      {icons[status as keyof typeof icons] || '○'}
    </span>
  );
}
```

**File: `ui/frontend/src/components/layout/TopBar.tsx`**

```typescript
import { SearchIcon, BellIcon, MoonIcon, SunIcon } from 'lucide-react';
import { useAppStore } from '@/store/appStore';

export function TopBar() {
  const { theme, setTheme } = useAppStore();

  return (
    <header className="h-16 bg-bg-secondary border-b border-border-subtle px-6 flex items-center justify-between">
      {/* Search */}
      <div className="flex-1 max-w-xl">
        <div className="relative">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
          <input
            type="text"
            placeholder="Search projects..."
            className="w-full pl-10 pr-4 py-2 bg-bg-tertiary rounded-lg border border-border-subtle focus:border-accent-cyan focus:outline-none text-sm"
          />
        </div>
      </div>

      {/* Right actions */}
      <div className="flex items-center space-x-4">
        {/* Notifications */}
        <button className="relative p-2 hover:bg-bg-hover rounded-lg transition-colors">
          <BellIcon className="w-5 h-5" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-accent-cyan rounded-full"></span>
        </button>

        {/* Theme toggle */}
        <button
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          className="p-2 hover:bg-bg-hover rounded-lg transition-colors"
        >
          {theme === 'dark' ? <MoonIcon className="w-5 h-5" /> : <SunIcon className="w-5 h-5" />}
        </button>
      </div>
    </header>
  );
}
```

### 4.8 Dashboard Page

**File: `ui/frontend/src/pages/DashboardPage.tsx`**

```typescript
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { projectsApi } from '@/api/client';
import { useAppStore } from '@/store/appStore';
import { useEffect } from 'react';
import { FSMVisualization } from '@/components/pipeline/FSMVisualization';
import { ControlPanel } from '@/components/pipeline/ControlPanel';
import { LiveLogs } from '@/components/pipeline/LiveLogs';
import { TokenDashboard } from '@/components/pipeline/TokenDashboard';
import { InfrastructureTab } from '@/components/infrastructure/InfrastructureTab';
import { EmptyState } from '@/components/shared/EmptyState';

export function DashboardPage() {
  const { projectId } = useParams();
  const { activeProject, activeTab, setActiveTab,openModal } = useAppStore();

  const { data: state } = useQuery({
    queryKey: ['project-state', projectId || activeProject?.id],
    queryFn: () => projectsApi.getState(Number(projectId || activeProject?.id)).then(res => res.data),
    enabled: !!(projectId || activeProject?.id),
    refetchInterval: 5000, // Poll every 5 seconds
  });

  if (!activeProject && !projectId) {
    return (
      <EmptyState
        icon="📁"
        title="No projects linked yet"
        description="Add a project to start monitoring pipeline execution"
        action={{
          label: 'Link New Project',
          onClick: () => openModal('linkProject'),
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-text-secondary">{activeProject?.name}</p>
        </div>
        <ControlPanel />
      </div>

      {/* Tabs */}
      <div className="border-b border-border-subtle">
        <nav className="flex space-x-8">
          {['state', 'git', 'costs', 'tests', 'infrastructure'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab as typeof activeTab)}
              className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab
                  ? 'border-accent-cyan text-accent-cyan'
                  : 'border-transparent text-text-secondary hover:text-text-primary'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="space-y-6">
        {activeTab === 'state' && (
          <>
            <FSMVisualization state={state} />
            <LiveLogs projectId={activeProject?.id} />
          </>
        )}

        {activeTab === 'git' && (
          <div className="bg-bg-secondary rounded-lg p-6">
            <p className="text-text-muted">Git visualization coming soon...</p>
          </div>
        )}

        {activeTab === 'costs' && <TokenDashboard projectId={activeProject?.id} />}

        {activeTab === 'tests' && (
          <div className="bg-bg-secondary rounded-lg p-6">
            <p className="text-text-muted">Test visualization coming soon...</p>
          </div>
        )}

        {activeTab === 'infrastructure' && <InfrastructureTab projectId={activeProject?.id} />}
      </div>
    </div>
  );
}
```

### 4.9 FSM Visualization Component

**File: `ui/frontend/src/components/pipeline/FSMVisualization.tsx`**

```typescript
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { motion } from 'framer-motion';
import { useMemo } from 'react';
import type { PipelineState } from '@/types';

interface FSMVisualizationProps {
  state: PipelineState | undefined;
}

export function FSMVisualization({ state }: FSMVisualizationProps) {
  const phases = [
    { id: 'prd_generation', label: 'PRD Gen' },
    { id: 'ralph_execution', label: 'Ralph Exec' },
    { id: 'qa_review', label: 'QA Review' },
    { id: 'merge_verify', label: 'Merge Verify' },
    { id: 'reconciliation', label: 'Reconcile' },
  ];

  const { nodes, edges } = useMemo(() => {
    const currentPhase = state?.milestones?.[state.current_milestone]?.phase;

    const nodes: Node[] = phases.map((phase, index) => {
      const status = currentPhase === phase.id ? 'active' : 'pending';

      return {
        id: phase.id,
        type: 'custom',
        position: { x: index * 200, y: 100 },
        data: {
          label: phase.label,
          status,
        },
      };
    });

    const edges: Edge[] = phases.slice(0, -1).map((phase, index) => ({
      id: `${phase.id}-${phases[index + 1].id}`,
      source: phase.id,
      target: phases[index + 1].id,
      animated: currentPhase === phase.id,
    }));

    return { nodes, edges };
  }, [state]);

  return (
    <div className="bg-bg-secondary rounded-lg p-6 h-96">
      <h2 className="text-lg font-semibold mb-4">Pipeline Status</h2>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={{
          custom: PhaseNode,
        }}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}

function PhaseNode({ data }: { data: { label: string; status: string } }) {
  const statusColors = {
    pending: 'border-text-muted bg-bg-tertiary',
    active: 'border-accent-cyan bg-bg-tertiary shadow-glow-cyan',
    complete: 'border-status-success bg-bg-tertiary',
    error: 'border-status-error bg-bg-tertiary shadow-glow-error',
  };

  return (
    <motion.div
      className={`px-6 py-4 rounded-lg border-2 ${
        statusColors[data.status as keyof typeof statusColors] || statusColors.pending
      }`}
      animate={
        data.status === 'active'
          ? { scale: [1, 1.05, 1], transition: { duration: 2, repeat: Infinity } }
          : {}
      }
    >
      <div className="text-center font-medium">{data.label}</div>
    </motion.div>
  );
}
```

### 4.10 Live Logs Component

**File: `ui/frontend/src/components/pipeline/LiveLogs.tsx`**

```typescript
import { useEffect, useRef, useState } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { DownloadIcon } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { WebSocketEvents } from '@/types';

interface LiveLogsProps {
  projectId?: number;
}

export function LiveLogs({ projectId }: LiveLogsProps) {
  const [logs, setLogs] = useState<Array<{ message: string; timestamp: string; level: string }>>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const { subscribe } = useWebSocket(projectId);

  useEffect(() => {
    if (!projectId) return;

    const unsubscribe = subscribe('log', (data: WebSocketEvents['log']) => {
      setLogs((prev) => {
        // Keep last 10,000 lines
        const newLogs = [...prev, data];
        return newLogs.slice(-10000);
      });
    });

    return unsubscribe;
  }, [projectId, subscribe]);

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    setAutoScroll(isAtBottom);
  };

  const downloadLogs = () => {
    const content = logs.map((log) => `[${log.timestamp}] ${log.message}`).join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs-${projectId}-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="bg-bg-secondary rounded-lg overflow-hidden">
      <div className="flex items-center justify-between p-4 border-b border-border-subtle">
        <h2 className="text-lg font-semibold">Live Output</h2>
        <button
          onClick={downloadLogs}
          className="flex items-center space-x-2 px-3 py-1.5 bg-bg-tertiary hover:bg-bg-hover rounded transition-colors text-sm"
        >
          <DownloadIcon className="w-4 h-4" />
          <span>Download</span>
        </button>
      </div>

      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-96 overflow-y-auto p-4 font-mono text-sm space-y-1"
      >
        {logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-text-muted">
            <p>📄</p>
            <p className="mt-2">No logs available</p>
            <p className="text-xs">Logs will appear when pipeline runs</p>
          </div>
        ) : (
          <AnimatePresence>
            {logs.map((log, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.15 }}
                className="text-text-secondary"
              >
                <span className="text-text-muted">[{new Date(log.timestamp).toLocaleTimeString()}]</span>{' '}
                {log.message}
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>

      {!autoScroll && (
        <div className="p-2 bg-bg-tertiary text-center">
          <button
            onClick={() => setAutoScroll(true)}
            className="text-sm text-accent-cyan hover:underline"
          >
            Resume auto-scroll
          </button>
        </div>
      )}
    </div>
  );
}
```

### 4.11 Control Panel Component

**File: `ui/frontend/src/components/pipeline/ControlPanel.tsx`**

```typescript
import { PlayIcon, StopIcon, RotateCcwIcon, HistoryIcon } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { pipelineApi } from '@/api/client';
import { useAppStore } from '@/store/appStore';

export function ControlPanel() {
  const { activeProject, openModal } = useAppStore();
  const queryClient = useQueryClient();

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

  const isRunning = activeProject?.status === 'running';
  const canResume = activeProject?.status === 'paused' || activeProject?.status === 'error';

  return (
    <div className="flex items-center space-x-3">
      {!isRunning ? (
        <button
          onClick={() => startMutation.mutate()}
          disabled={!activeProject || startMutation.isPending}
          className="flex items-center space-x-2 px-4 py-2 bg-accent-cyan text-white rounded-lg hover:bg-accent-cyan/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <PlayIcon className="w-5 h-5" />
          <span>Start Pipeline</span>
        </button>
      ) : (
        <button
          onClick={() => stopMutation.mutate()}
          disabled={stopMutation.isPending}
          className="flex items-center space-x-2 px-4 py-2 bg-status-error text-white rounded-lg hover:bg-status-error/90 disabled:opacity-50 transition-colors"
        >
          <StopIcon className="w-5 h-5" />
          <span>Stop</span>
        </button>
      )}

      {canResume && (
        <button
          onClick={() => resumeMutation.mutate()}
          disabled={resumeMutation.isPending}
          className="flex items-center space-x-2 px-4 py-2 border border-accent-cyan text-accent-cyan rounded-lg hover:bg-accent-cyan/10 disabled:opacity-50 transition-colors"
        >
          <RotateCcwIcon className="w-5 h-5" />
          <span>Resume</span>
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
    </div>
  );
}
```

---

## 5. Database Implementation

### 5.1 Alembic Setup

**File: `ui/backend/alembic.ini`**

```ini
[alembic]
script_location = migrations
prepend_sys_path = .
sqlalchemy.url = sqlite:///data/pipeline.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

**File: `ui/backend/migrations/env.py`**

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from database import db
from models import *

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = db.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### 5.2 Initial Migration

```bash
cd ui/backend
alembic init migrations
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

---

## 6. Infrastructure Integration

### 6.1 Pipeline Configurator Invoker

**File: `ui/backend/services/configurator_invoker.py`**

```python
"""Service to invoke pipeline configurator."""

import os
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from database import db
from models import ProjectSetup, InfrastructureBackup

class ConfiguratorInvoker:
    """Invokes pipeline configurator and handles validation loop."""
    
    def __init__(self, project):
        self.project = project
        self.setup = None
        self.max_fix_attempts = 3
    
    def run_setup(self):
        """Run the full setup process."""
        try:
            # Create setup record
            self.setup = ProjectSetup(
                project_id=self.project.id,
                status='checking',
                current_step='pre-check',
                progress=10
            )
            db.session.add(self.setup)
            db.session.commit()
            
            # Step 1: Backup existing files
            self._backup_infrastructure()
            
            # Step 2: Invoke configurator
            self.setup.status = 'configuring'
            self.setup.current_step = 'pipeline_configurator'
            self.setup.progress = 30
            db.session.commit()
            
            self._invoke_configurator()
            
            # Step 3: Validate
            self.setup.status = 'validating'
            self.setup.current_step = 'test_environment_validation'
            self.setup.progress = 60
            db.session.commit()
            
            for attempt in range(self.max_fix_attempts):
                validation_result = self._validate_environment()
                
                if validation_result['status'] == 'passed':
                    # Success!
                    self.setup.status = 'complete'
                    self.setup.progress = 100
                    self.setup.completed_at = datetime.utcnow()
                    self.project.status = 'ready'
                    db.session.commit()
                    return
                
                # Auto-fix
                if attempt < self.max_fix_attempts - 1:
                    self.setup.status = 'fixing'
                    self.setup.auto_fix_attempts = attempt + 1
                    db.session.commit()
                    
                    self._auto_fix(validation_result)
            
            # Failed after max attempts
            self.setup.status = 'intervention'
            self.setup.current_step = 'manual_intervention_required'
            self.setup.progress = 80
            self.project.status = 'error'
            db.session.commit()
            
        except Exception as e:
            self.setup.status = 'failed'
            self.project.status = 'error'
            db.session.commit()
            print(f"Setup failed: {e}")
    
    def _backup_infrastructure(self):
        """Backup existing docker-compose files."""
        project_path = Path(self.project.root_path)
        backup_dir = project_path / '.ralph' / 'backup' / datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        files_to_backup = [
            'docker-compose.yml',
            'docker-compose.test.yml',
            'pipeline-config.json'
        ]
        
        backed_up = []
        for file in files_to_backup:
            src = project_path / file
            if src.exists():
                dst = backup_dir / file
                shutil.copy2(src, dst)
                backed_up.append(file)
        
        backup = InfrastructureBackup(
            project_id=self.project.id,
            backup_path=str(backup_dir),
            files_backed_up=json.dumps(backed_up)
        )
        db.session.add(backup)
        db.session.commit()
    
    def _invoke_configurator(self):
        """Invoke pipeline configurator skill."""
        # This would call: claude /pipeline_configurator with docs/ context
        # For now, simulate with subprocess
        
        cmd = [
            'claude',
            '/pipeline_configurator',
            '--project', self.project.root_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project.root_path
        )
        
        self.setup.configurator_output = result.stdout
        db.session.commit()
        
        if result.returncode != 0:
            raise Exception(f"Configurator failed: {result.stderr}")
    
    def _validate_environment(self):
        """Run validation command."""
        cmd = [
            'ralph-pipeline',
            'validate-test-env',
            '--config', self.project.config_path,
            '--output', 'json'
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        validation_result = json.loads(result.stdout)
        self.setup.validation_report = json.dumps(validation_result)
        db.session.commit()
        
        return validation_result
    
    def _auto_fix(self, validation_result):
        """Attempt to auto-fix validation errors."""
        # Pass validation report back to configurator
        # Configurator analyzes and fixes issues
        
        # For now, just re-invoke configurator with validation context
        self._invoke_configurator()
```

### 6.2 CLI validate-test-env Command

Add to existing ralph-pipeline CLI:

**File: `src/ralph_pipeline/cli.py` (add new subcommand)**

```python
# Add to existing CLI

# validate-test-env subcommand
validate_parser = subparsers.add_parser(
    'validate-test-env', help='Validate test environment infrastructure'
)
validate_parser.add_argument(
    '--config', required=True, help='Path to pipeline-config.json'
)
validate_parser.add_argument(
    '--output', choices=['text', 'json'], default='text', help='Output format'
)
validate_parser.add_argument(
    '--timeout', type=int, default=30, help='Timeout for each check (seconds)'
)

def validate_test_environment(args: argparse.Namespace):
    """Validate test environment."""
    from ralph_pipeline.infra.test_runner import TestInfraValidator
    
    config = PipelineConfig.load(Path(args.config))
    validator = TestInfraValidator(config, timeout=args.timeout)
    
    report = validator.run_validation()
    
    if args.output == 'json':
        print(json.dumps(report, indent=2))
    else:
        validator.print_report(report)
    
    sys.exit(0 if report['status'] == 'passed' else 1)

# Add to command handler
if args.command == 'validate-test-env':
    validate_test_environment(args)
```

---

## 7. Testing Implementation

### 7.1 Backend Tests

**File: `ui/backend/tests/test_api_projects.py`**

```python
"""Tests for projects API."""

import pytest
from app import app, db
from models import Project

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.drop_all()

def test_list_projects_empty(client):
    """Test listing projects when none exist."""
    response = client.get('/api/projects')
    assert response.status_code == 200
    assert response.json == []

def test_create_project(client, tmp_path):
    """Test creating a project."""
    # Create test project directory
    project_path = tmp_path / 'test-project'
    project_path.mkdir()
    (project_path / 'pipeline-config.json').write_text('{}')
    
    response = client.post('/api/projects', json={
        'project_path': str(project_path)
    })
    
    assert response.status_code == 201
    data = response.json
    assert data['name'] == 'test-project'
    assert data['root_path'] == str(project_path)

def test_pre_check_valid(client, tmp_path):
    """Test pre-check with valid project."""
    project_path = tmp_path / 'test-project'
    project_path.mkdir()
    
    # Create required docs
    for doc in ['01-requirements', '02-architecture', '03-design', 
                '04-test-architecture', '05-milestones']:
        doc_path = project_path / 'docs' / doc
        doc_path.mkdir(parents=True)
        (doc_path / 'handover.json').write_text('{}')
    
    response = client.post('/api/projects/pre-check', json={
        'project_path': str(project_path)
    })
    
    assert response.status_code == 200
    data = response.json
    assert data['valid'] is True
```

### 7.2 Frontend Tests

**File: `ui/frontend/src/components/layout/Sidebar.test.tsx`**

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { Sidebar } from './Sidebar';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>{children}</BrowserRouter>
  </QueryClientProvider>
);

describe('Sidebar', () => {
  it('renders project list', () => {
    render(<Sidebar />, { wrapper });
    expect(screen.getByText('Projects')).toBeInTheDocument();
  });

  it('shows add project button', () => {
    render(<Sidebar />, { wrapper });
    const addButton = screen.getByTitle('Add Project');
    expect(addButton).toBeInTheDocument();
  });
});
```

---

## 8. Deployment

### 8.1 Docker Configuration

**File: `ui/docker-compose.yml`**

```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - /var/run/docker.sock:/var/run/docker.sock
      - ${HOST_PROJECTS_ROOT:-/home/user/projects}:/projects
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=sqlite:///data/pipeline.db
      - SECRET_KEY=${SECRET_KEY}
      - CORS_ORIGINS=http://localhost:5000
    networks:
      - pipeline-net
    restart: unless-stopped

networks:
  pipeline-net:
    driver: bridge

volumes:
  data:
```

**File: `ui/Dockerfile.backend`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Create data directory
RUN mkdir -p /app/data

# Initialize database
RUN python -c "from app import app, db; app.app_context().push(); db.create_all()"

EXPOSE 5000

CMD ["python", "app.py"]
```

### 8.2 Production Build Script

**File: `ui/build.sh`**

```bash
#!/bin/bash
set -e

echo "Building Ralph Pipeline UI..."

# Build frontend
cd frontend
npm install
npm run build
cd ..

# Backend is already set up
echo "Build complete!"
echo ""
echo "To run in production:"
echo "  docker-compose up -d"
echo ""
echo "Access the UI at: http://localhost:5000"
```

### 8.3 Development Startup Script

**File: `ui/dev.sh`**

```bash
#!/bin/bash

# Start backend
cd backend
source venv/bin/activate
python app.py &
BACKEND_PID=$!
cd ..

# Start frontend
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo "Backend running on http://localhost:5000"
echo "Frontend running on http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait
```

---

## 9. Common Patterns

### 9.1 Error Handling Pattern

```typescript
// Frontend
try {
  const response = await projectsApi.create(data);
  queryClient.invalidateQueries({ queryKey: ['projects'] });
  toast.success('Project created successfully');
} catch (error) {
  if (axios.isAxiosError(error)) {
    const message = error.response?.data?.error || 'An error occurred';
    toast.error(message);
  }
}
```

```python
# Backend
try:
    # Operation
    db.session.commit()
    return jsonify({'success': True}), 200
except Exception as e:
    db.session.rollback()
    return jsonify({'error': str(e)}), 500
```

### 9.2 WebSocket Event Pattern

```python
# Backend emitting
from app import socketio
from api.websocket import emit_log

emit_log(socketio, project_id, {
    'project_id': project_id,
    'message': 'Test started',
    'timestamp': datetime.utcnow().isoformat()
})
```

```typescript
// Frontend receiving
useEffect(() => {
  const unsubscribe = subscribe('log', (data) => {
    console.log('New log:', data);
    setLogs(prev => [...prev, data]);
  });
  
  return unsubscribe;
}, []);
```

---

## 10. Troubleshooting

### 10.1 Common Issues

**Issue: WebSocket connection fails**
```
Solution:
- Check CORS_ORIGINS includes frontend URL
- Ensure eventlet is installed
- Verify socket.io client version matches server
```

**Issue: Database locked**
```
Solution:
- SQLite doesn't handle concurrent writes well
- Use proper transaction management
- Consider connection pooling
```

**Issue: File watcher not detecting changes**
```
Solution:
- Check Watchdog is running
- Verify .ralph/ directory exists
- Check file permissions
```

**Issue: Monaco editor not loading**
```
Solution:
- Ensure monaco-editor is in dependencies (not devDependencies)
- Check Vite config for proper asset handling
- Verify Content-Security-Policy allows workers
```

---

## 11. Final Checklist

Before deployment:

- [ ] All environment variables configured in `.env`
- [ ] Database migrated (`alembic upgrade head`)
- [ ] Frontend built (`npm run build`)
- [ ] Backend can access host Docker socket
- [ ] Ralph Pipeline CLI available in PATH
- [ ] Claude CLI configured and accessible
- [ ] Project paths properly mounted in Docker
- [ ] WebSocket connection tested
- [ ] File watching operational
- [ ] All tests passing
- [ ] Lock file mechanism verified
- [ ] Backup/restore functionality tested

---

## Conclusion

This guide provides a complete implementation specification for the Ralph Pipeline UI. Follow the structure and patterns defined here to build a robust, production-ready web application.

**Key Points:**
- Backend uses Flask + SocketIO for real-time updates
- Frontend uses React + TypeScript with modern tooling
- Infrastructure validation is automated with auto-fix loops
- CLI remains fully functional alongside UI
- All states and events are properly tracked
- Testing coverage for critical paths

**Next Steps:**
1. Set up development environment
2. Implement backend API endpoints
3. Build frontend components
4. Integrate infrastructure validation
5. Add comprehensive testing
6. Deploy using Docker Compose

Good luck with the implementation!
