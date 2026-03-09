import { pipelineApi, projectsApi } from '@/api/client';
import { useAppStore } from '@/store/appStore';
import type { PipelineOverview, Project } from '@/types';
import { useQueries, useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
    ActivityIcon,
    DollarSignIcon,
    FolderPlusIcon,
    LayersIcon,
    TrendingUpIcon,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

// ── Status colors ───────────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  initialized: { bg: 'bg-text-muted/15', text: 'text-text-muted', label: 'Initialized' },
  ready: { bg: 'bg-accent-cyan/15', text: 'text-accent-cyan', label: 'Ready' },
  running: { bg: 'bg-accent-cyan/15', text: 'text-accent-cyan', label: 'Running' },
  paused: { bg: 'bg-status-warning/15', text: 'text-status-warning', label: 'Paused' },
  error: { bg: 'bg-status-error/15', text: 'text-status-error', label: 'Error' },
  success: { bg: 'bg-status-success/15', text: 'text-status-success', label: 'Complete' },
  configuring: { bg: 'bg-accent-purple/15', text: 'text-accent-purple', label: 'Configuring' },
  stopped: { bg: 'bg-status-warning/15', text: 'text-status-warning', label: 'Stopped' },
};

function getStatusStyle(status: string) {
  return STATUS_STYLES[status] ?? { bg: 'bg-text-muted/15', text: 'text-text-muted', label: status };
}

function formatCost(usd: number): string {
  if (usd === 0) return '$0.00';
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  if (usd < 1) return `$${usd.toFixed(3)}`;
  return `$${usd.toFixed(2)}`;
}

// ── Project Card ────────────────────────────────────────────────────────────

interface ProjectCardProps {
  project: Project;
  overview: PipelineOverview | undefined;
  isLoadingOverview: boolean;
}

function ProjectCard({ project, overview, isLoadingOverview }: ProjectCardProps) {
  const { setActiveProject } = useAppStore();
  const navigate = useNavigate();
  const statusStyle = getStatusStyle(project.status);

  const progress = overview?.progress.percentage ?? 0;
  const totalCost = overview?.cost.total_usd ?? 0;
  const completedMilestones = overview?.progress.completed_milestones ?? 0;
  const totalMilestones = overview?.progress.total_milestones ?? 0;
  const currentPhase = overview?.progress.current_phase;

  return (
    <motion.button
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4, transition: { duration: 0.15 } }}
      whileTap={{ scale: 0.98 }}
      onClick={() => {
        setActiveProject(project);
        navigate(`/dashboard/${project.id}`);
      }}
      className="bg-bg-secondary rounded-xl border border-border-subtle p-5 text-left w-full hover:border-accent-cyan/40 transition-colors group"
    >
      {/* Header: Name + Status */}
      <div className="flex items-start justify-between mb-4">
        <div className="min-w-0 flex-1 mr-3">
          <h3 className="text-base font-semibold text-text-primary truncate group-hover:text-accent-cyan transition-colors">
            {project.name}
          </h3>
          <p className="text-xs text-text-muted truncate mt-0.5">{project.root_path}</p>
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${statusStyle.bg} ${statusStyle.text}`}>
          {statusStyle.label}
        </span>
      </div>

      {/* Progress bar */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-text-muted">Progress</span>
          <span className="text-xs font-semibold text-text-primary">{Math.round(progress)}%</span>
        </div>
        <div className="h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-accent-cyan"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
          />
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-2">
        <div className="flex items-center gap-1.5">
          <LayersIcon className="w-3.5 h-3.5 text-accent-purple shrink-0" />
          <div className="min-w-0">
            <p className="text-xs text-text-muted leading-none">Milestones</p>
            {isLoadingOverview ? (
              <div className="h-3.5 w-8 bg-bg-tertiary rounded mt-0.5" />
            ) : (
              <p className="text-sm font-semibold text-text-primary leading-tight mt-0.5">
                {completedMilestones}/{totalMilestones}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <DollarSignIcon className="w-3.5 h-3.5 text-status-success shrink-0" />
          <div className="min-w-0">
            <p className="text-xs text-text-muted leading-none">Cost</p>
            {isLoadingOverview ? (
              <div className="h-3.5 w-10 bg-bg-tertiary rounded mt-0.5" />
            ) : (
              <p className="text-sm font-semibold text-text-primary leading-tight mt-0.5">
                {formatCost(totalCost)}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <ActivityIcon className="w-3.5 h-3.5 text-accent-cyan shrink-0" />
          <div className="min-w-0">
            <p className="text-xs text-text-muted leading-none">Phase</p>
            {isLoadingOverview ? (
              <div className="h-3.5 w-12 bg-bg-tertiary rounded mt-0.5" />
            ) : (
              <p className="text-xs font-medium text-text-primary leading-tight mt-0.5 truncate">
                {currentPhase
                  ? currentPhase.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
                  : '—'}
              </p>
            )}
          </div>
        </div>
      </div>
    </motion.button>
  );
}

// ── Add Project Card ────────────────────────────────────────────────────────

function AddProjectCard() {
  const { openModal } = useAppStore();

  return (
    <motion.button
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4, transition: { duration: 0.15 } }}
      whileTap={{ scale: 0.98 }}
      onClick={() => openModal('linkProject')}
      className="rounded-xl border-2 border-dashed border-border-subtle p-5 text-center w-full hover:border-accent-cyan/40 hover:bg-bg-secondary/50 transition-colors group min-h-[200px] flex flex-col items-center justify-center gap-3"
    >
      <div className="w-12 h-12 rounded-xl bg-bg-tertiary flex items-center justify-center group-hover:bg-accent-cyan/10 transition-colors">
        <FolderPlusIcon className="w-6 h-6 text-text-muted group-hover:text-accent-cyan transition-colors" />
      </div>
      <div>
        <p className="text-sm font-medium text-text-secondary group-hover:text-text-primary transition-colors">
          Link New Project
        </p>
        <p className="text-xs text-text-muted mt-0.5">Add an existing project to monitor</p>
      </div>
    </motion.button>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────

export function ProjectsOverview() {
  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list().then((res) => res.data),
  });

  // Fetch overview data for each project (for progress, cost, etc.)
  const overviewQueries = useQueries({
    queries: (projects ?? []).map((project) => ({
      queryKey: ['overview', project.id],
      queryFn: () => pipelineApi.getOverview(project.id).then((res) => res.data),
      enabled: !!project.is_setup,
      staleTime: 10_000,
      refetchInterval: 5_000,
    })),
  });

  // Build lookup: projectId → overview data
  const overviewMap = new Map<number, PipelineOverview>();
  (projects ?? []).forEach((project, i) => {
    const query = overviewQueries[i];
    if (query?.data) {
      overviewMap.set(project.id, query.data);
    }
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Projects</h1>
          <p className="text-text-secondary text-sm mt-1">Overview of all linked projects</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-bg-secondary rounded-xl border border-border-subtle p-5 animate-pulse">
              <div className="flex items-start justify-between mb-4">
                <div className="space-y-2 flex-1">
                  <div className="h-5 w-32 bg-bg-tertiary rounded" />
                  <div className="h-3 w-48 bg-bg-tertiary rounded" />
                </div>
                <div className="h-5 w-16 bg-bg-tertiary rounded-full" />
              </div>
              <div className="h-1.5 bg-bg-tertiary rounded-full mb-4" />
              <div className="grid grid-cols-3 gap-2">
                {[1, 2, 3].map((j) => (
                  <div key={j} className="h-8 bg-bg-tertiary rounded" />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Summary stats
  const totalProjects = projects?.length ?? 0;
  const runningCount = projects?.filter((p) => p.status === 'running').length ?? 0;
  const totalCost = Array.from(overviewMap.values()).reduce((sum, o) => sum + o.cost.total_usd, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Projects</h1>
          <p className="text-text-secondary text-sm mt-1">Overview of all linked projects</p>
        </div>

        {totalProjects > 0 && (
          <div className="flex items-center gap-5 text-sm">
            <div className="flex items-center gap-1.5">
              <LayersIcon className="w-4 h-4 text-text-muted" />
              <span className="text-text-muted">{totalProjects} project{totalProjects !== 1 ? 's' : ''}</span>
            </div>
            {runningCount > 0 && (
              <div className="flex items-center gap-1.5">
                <TrendingUpIcon className="w-4 h-4 text-accent-cyan" />
                <span className="text-accent-cyan">{runningCount} running</span>
              </div>
            )}
            {totalCost > 0 && (
              <div className="flex items-center gap-1.5">
                <DollarSignIcon className="w-4 h-4 text-status-success" />
                <span className="text-text-muted">{formatCost(totalCost)} total</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Project Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {(projects ?? []).map((project, i) => (
          <ProjectCard
            key={project.id}
            project={project}
            overview={overviewMap.get(project.id)}
            isLoadingOverview={overviewQueries[i]?.isLoading ?? false}
          />
        ))}
        <AddProjectCard />
      </div>
    </div>
  );
}
