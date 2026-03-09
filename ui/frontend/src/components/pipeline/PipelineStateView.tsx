/**
 * PipelineStateView — deep milestone & phase inspection view.
 *
 * Shows every milestone as an expandable card with:
 * - Color-coded border and status icon (at a glance)
 * - Compact phase strip showing all phases with status
 * - Bugfix cycle count
 * - Expandable FSM visualization + logs per milestone
 *
 * The active milestone is auto-expanded. All milestone states are
 * visible without clicking through.
 */

import { pipelineApi } from '@/api/client';
import { PhaseFSM } from '@/components/pipeline/PhaseFSM';
import { useWebSocket } from '@/hooks/useWebSocket';
import type { ExecutionLog, MilestoneInfo, WebSocketEvents } from '@/types';
import { useQuery } from '@tanstack/react-query';
import clsx from 'clsx';
import { AnimatePresence, motion } from 'framer-motion';
import {
    AlertTriangleIcon,
    BugIcon,
    CheckCircle2Icon,
    ChevronDownIcon,
    CircleDotIcon,
    ClockIcon,
    DownloadIcon,
    FileTextIcon,
    LayersIcon,
    Loader2Icon,
    PauseCircleIcon,
    ScrollTextIcon,
    SearchIcon,
    XCircleIcon,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

interface PipelineStateViewProps {
  projectId: number;
  milestones: MilestoneInfo[];
  maxBugfixCycles: number;
  pipelineStatus: string;
}

// ── Phase definitions ─────────────────────────────────────────────────────────

const MAIN_PHASES = [
  { id: 'prd_generation', label: 'PRD', short: 'PRD' },
  { id: 'ralph_execution', label: 'Execution', short: 'EXEC' },
  { id: 'qa_review', label: 'QA Review', short: 'QA' },
  { id: 'reconciliation', label: 'Reconciliation', short: 'RECON' },
];

const PHASE0_PHASES = [
  { id: 'phase0_scaffolding', label: 'Scaffolding', short: 'SCAF' },
  { id: 'phase0_test_infra', label: 'Test Infra', short: 'TEST' },
  { id: 'phase0_lifecycle', label: 'Lifecycle', short: 'LIFE' },
];

const PHASE_ORDER = new Map<string, number>();
['pending', 'prd_generation', 'ralph_execution', 'qa_review', 'reconciliation', 'complete'].forEach(
  (p, i) => PHASE_ORDER.set(p, i)
);

const PHASE0_ORDER = new Map<string, number>();
['pending', 'phase0_scaffolding', 'phase0_test_infra', 'phase0_lifecycle', 'complete'].forEach(
  (p, i) => PHASE0_ORDER.set(p, i)
);

// ── Status helpers ────────────────────────────────────────────────────────────

type MilestoneStatus = 'completed' | 'active' | 'paused' | 'failed' | 'pending';

function getMilestoneStatus(m: MilestoneInfo, pipelineStatus: string): MilestoneStatus {
  if (m.completed_at || m.phase === 'complete') return 'completed';
  if (m.phase === 'failed') return 'failed';
  if (m.started_at && m.phase !== 'pending') {
    return pipelineStatus === 'running' ? 'active' : 'paused';
  }
  return 'pending';
}

type PhaseStatus = 'completed' | 'active' | 'paused' | 'failed' | 'pending';

function getPhaseStatus(
  phaseId: string,
  currentPhase: string,
  isComplete: boolean,
  isFailed: boolean,
  pipelineStatus: string,
  orderMap: Map<string, number>
): PhaseStatus {
  if (isComplete) return 'completed';
  if (isFailed) {
    const currentIdx = orderMap.get(currentPhase) ?? -1;
    const phaseIdx = orderMap.get(phaseId) ?? -1;
    if (phaseIdx < currentIdx) return 'completed';
    if (phaseIdx === currentIdx) return 'failed';
    return 'pending';
  }
  const currentIdx = orderMap.get(currentPhase) ?? -1;
  const phaseIdx = orderMap.get(phaseId) ?? -1;
  if (phaseIdx < currentIdx) return 'completed';
  if (phaseIdx === currentIdx) return pipelineStatus === 'running' ? 'active' : 'paused';
  return 'pending';
}

const STATUS_STYLES: Record<MilestoneStatus, {
  border: string;
  bg: string;
  iconColor: string;
  label: string;
}> = {
  completed: {
    border: 'border-status-success/50',
    bg: 'bg-status-success/5',
    iconColor: 'text-status-success',
    label: 'Complete',
  },
  active: {
    border: 'border-accent-blue/60',
    bg: 'bg-accent-blue/5',
    iconColor: 'text-accent-blue',
    label: 'Active',
  },
  paused: {
    border: 'border-status-warning/40',
    bg: 'bg-status-warning/5',
    iconColor: 'text-status-warning',
    label: 'Paused',
  },
  failed: {
    border: 'border-status-error/50',
    bg: 'bg-status-error/5',
    iconColor: 'text-status-error',
    label: 'Failed',
  },
  pending: {
    border: 'border-border-subtle',
    bg: 'bg-bg-secondary/50',
    iconColor: 'text-text-muted',
    label: 'Pending',
  },
};

const PHASE_STATUS_STYLES: Record<PhaseStatus, { bg: string; text: string; border: string }> = {
  completed: { bg: 'bg-status-success/15', text: 'text-status-success', border: 'border-status-success/30' },
  active: { bg: 'bg-accent-blue/15', text: 'text-accent-blue', border: 'border-accent-blue/30' },
  paused: { bg: 'bg-status-warning/15', text: 'text-status-warning', border: 'border-status-warning/30' },
  failed: { bg: 'bg-status-error/15', text: 'text-status-error', border: 'border-status-error/30' },
  pending: { bg: 'bg-bg-tertiary/40', text: 'text-text-muted', border: 'border-border-subtle' },
};

function StatusIcon({ status, size = 18 }: { status: MilestoneStatus; size?: number }) {
  const s = { width: size, height: size };
  switch (status) {
    case 'completed':
      return <CheckCircle2Icon style={s} className="text-status-success" />;
    case 'active':
      return (
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
          className="flex items-center"
        >
          <Loader2Icon style={s} className="text-accent-blue" />
        </motion.div>
      );
    case 'paused':
      return <PauseCircleIcon style={s} className="text-status-warning" />;
    case 'failed':
      return <XCircleIcon style={s} className="text-status-error" />;
    default:
      return <CircleDotIcon style={s} className="text-text-muted" />;
  }
}

// ── Phase mini-icon ───────────────────────────────────────────────────────────

function PhaseIcon({ status }: { status: PhaseStatus }) {
  const w = 'w-3 h-3';
  switch (status) {
    case 'completed':
      return <CheckCircle2Icon className={`${w} text-status-success`} />;
    case 'active':
      return (
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
          className="flex items-center"
        >
          <Loader2Icon className={`${w} text-accent-blue`} />
        </motion.div>
      );
    case 'failed':
      return <XCircleIcon className={`${w} text-status-error`} />;
    default:
      return <CircleDotIcon className={`${w} text-text-muted`} />;
  }
}

// ── Compact phase strip ───────────────────────────────────────────────────────

function PhaseStrip({
  milestone,
  pipelineStatus,
}: {
  milestone: MilestoneInfo;
  pipelineStatus: string;
}) {
  const isPhase0 = milestone.id === 0;
  const phases = isPhase0 ? PHASE0_PHASES : MAIN_PHASES;
  const orderMap = isPhase0 ? PHASE0_ORDER : PHASE_ORDER;
  const isComplete = !!milestone.completed_at || milestone.phase === 'complete';
  const isFailed = milestone.phase === 'failed';

  return (
    <div className="flex items-center gap-1">
      {phases.map((phase, i) => {
        const status = getPhaseStatus(
          phase.id,
          milestone.phase,
          isComplete,
          isFailed,
          pipelineStatus,
          orderMap
        );
        const styles = PHASE_STATUS_STYLES[status];

        return (
          <div key={phase.id} className="flex items-center gap-1">
            <div
              className={clsx(
                'flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] font-medium',
                styles.bg,
                styles.text,
                styles.border
              )}
            >
              <PhaseIcon status={status} />
              <span>{phase.short}</span>
            </div>
            {i < phases.length - 1 && (
              <span className="text-text-muted text-[10px]">→</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Log viewer for a milestone ────────────────────────────────────────────────

function MilestoneLogViewer({
  projectId,
  milestone,
  pipelineStatus,
}: {
  projectId: number;
  milestone: MilestoneInfo;
  pipelineStatus: string;
}) {
  const [logFilter, setLogFilter] = useState<string>('');
  const [levelFilter, setLevelFilter] = useState<'all' | 'error' | 'warning' | 'info'>('all');
  const [liveLogs, setLiveLogs] = useState<
    Array<{ message: string; timestamp: string; level: string }>
  >([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const { subscribe } = useWebSocket(projectId);

  // Fetch historical logs
  const { data: historicalLogs } = useQuery({
    queryKey: ['milestone-logs', projectId, milestone.id],
    queryFn: () =>
      pipelineApi
        .getLogs(projectId, { milestone_id: milestone.id, limit: 2000 })
        .then((res) => res.data),
    enabled: !!projectId,
    refetchInterval: pipelineStatus === 'running' ? 5000 : false,
  });

  // Subscribe to live logs
  useEffect(() => {
    if (!projectId) return;

    const unsubscribe = subscribe('log', (data: WebSocketEvents['log']) => {
      if (data.milestone_id && data.milestone_id !== milestone.id) return;
      setLiveLogs((prev) => {
        const newLogs = [
          ...prev,
          {
            message: data.message,
            timestamp: data.timestamp,
            level: data.level || 'info',
          },
        ];
        return newLogs.slice(-5000);
      });
    });

    return () => {
      unsubscribe();
      setLiveLogs([]);
    };
  }, [projectId, milestone.id, subscribe]);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [liveLogs, historicalLogs, autoScroll]);

  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 50);
  }, []);

  // Merge logs
  const allLogs = useMemo(() => {
    const historical = (historicalLogs || []).map((log: ExecutionLog) => ({
      message: log.message,
      timestamp: log.created_at,
      level: log.log_level,
    }));
    const reversed = [...historical].reverse();
    const lastTs = reversed.length > 0 ? reversed[reversed.length - 1].timestamp : '';
    const newLive = liveLogs.filter((l) => l.timestamp > lastTs);
    return [...reversed, ...newLive];
  }, [historicalLogs, liveLogs]);

  // Filter logs
  const filteredLogs = useMemo(() => {
    return allLogs.filter((log) => {
      if (levelFilter !== 'all' && log.level !== levelFilter) return false;
      if (logFilter && !log.message.toLowerCase().includes(logFilter.toLowerCase()))
        return false;
      return true;
    });
  }, [allLogs, levelFilter, logFilter]);

  const downloadLogs = () => {
    const content = filteredLogs
      .map((log) => `[${log.timestamp}] [${log.level}] ${log.message}`)
      .join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs-m${milestone.id}-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const levelColor: Record<string, string> = {
    error: 'text-status-error',
    warning: 'text-status-warning',
    info: 'text-text-secondary',
    debug: 'text-text-muted',
  };

  const errorCount = allLogs.filter((l) => l.level === 'error').length;
  const warningCount = allLogs.filter((l) => l.level === 'warning').length;

  return (
    <div className="mt-3 rounded-lg border border-white/[0.06] bg-bg-primary/30 overflow-hidden">
      {/* Log header with filters */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/[0.06] bg-bg-secondary/50">
        <div className="flex items-center gap-2">
          <ScrollTextIcon className="w-3.5 h-3.5 text-accent-violet" />
          <span className="text-xs font-medium text-text-primary">
            Logs ({filteredLogs.length})
          </span>
          {errorCount > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-status-error/20 text-status-error">
              {errorCount} errors
            </span>
          )}
          {warningCount > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-status-warning/20 text-status-warning">
              {warningCount} warnings
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Level filter */}
          <div className="flex items-center gap-0.5 p-0.5 bg-bg-tertiary rounded-md">
            {(['all', 'error', 'warning', 'info'] as const).map((level) => (
              <button
                key={level}
                onClick={() => setLevelFilter(level)}
                className={clsx(
                  'px-2 py-0.5 text-[10px] rounded transition-colors',
                  levelFilter === level
                    ? 'bg-bg-secondary text-text-primary shadow-sm'
                    : 'text-text-muted hover:text-text-secondary'
                )}
              >
                {level === 'all' ? 'All' : level.charAt(0).toUpperCase() + level.slice(1)}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative">
            <SearchIcon className="w-3 h-3 text-text-muted absolute left-2 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={logFilter}
              onChange={(e) => setLogFilter(e.target.value)}
              placeholder="Search logs..."
              className="w-32 pl-6 pr-2 py-1 text-[10px] bg-bg-tertiary rounded border border-border-subtle text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-cyan/50"
            />
          </div>

          {/* Download */}
          <button
            onClick={downloadLogs}
            className="p-1 hover:bg-bg-hover rounded transition-colors"
            title="Download logs"
          >
            <DownloadIcon className="w-3.5 h-3.5 text-text-muted" />
          </button>
        </div>
      </div>

      {/* Log content */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="max-h-[250px] overflow-y-auto p-3 font-mono text-[11px] space-y-0.5"
      >
        {filteredLogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-6 text-text-muted">
            <p className="text-sm">No logs</p>
            <p className="text-[10px] mt-0.5">
              {allLogs.length > 0
                ? 'No logs match current filters'
                : 'Logs will appear when this milestone runs'}
            </p>
          </div>
        ) : (
          filteredLogs.map((log, index) => (
            <div
              key={`${log.timestamp}-${index}`}
              className={clsx(
                levelColor[log.level] || 'text-text-secondary',
                log.level === 'error' && 'bg-status-error/5 px-1.5 py-0.5 rounded -mx-1.5'
              )}
            >
              <span className="text-text-muted">
                [{new Date(log.timestamp).toLocaleTimeString()}]
              </span>{' '}
              <span
                className={clsx(
                  'font-semibold',
                  log.level === 'error' && 'text-status-error',
                  log.level === 'warning' && 'text-status-warning'
                )}
              >
                {log.level !== 'info' && `[${log.level.toUpperCase()}] `}
              </span>
              {log.message}
            </div>
          ))
        )}
      </div>

      {/* Auto-scroll indicator */}
      {!autoScroll && filteredLogs.length > 0 && (
        <div className="px-3 py-1 bg-bg-tertiary text-center border-t border-border-subtle">
          <button
            onClick={() => setAutoScroll(true)}
            className="text-[10px] text-accent-cyan hover:underline"
          >
            ↓ Scroll to bottom
          </button>
        </div>
      )}
    </div>
  );
}

// ── Log File Viewer (reads .ralph/logs/<dir>/<file>.log) ──────────────────────

function LogFileViewer({
  projectId,
  milestone,
  pipelineStatus,
}: {
  projectId: number;
  milestone: MilestoneInfo;
  pipelineStatus: string;
}) {
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);

  // Determine the log directory name for this milestone
  const dirName = milestone.id === 0
    ? 'phase0'
    : milestone.slug
      ? `m${milestone.id}-${milestone.slug}`
      : `m${milestone.id}`;

  // Fetch available log files
  const { data: logFiles } = useQuery({
    queryKey: ['logfiles', projectId],
    queryFn: () => pipelineApi.getLogFiles(projectId).then((r) => r.data),
    enabled: !!projectId,
    refetchInterval: pipelineStatus === 'running' ? 5000 : false,
  });

  // Get files for this milestone's directory
  const availableFiles = logFiles?.directories?.[dirName] ?? [];

  // Auto-select first file if none selected
  useEffect(() => {
    if (!selectedFile && availableFiles.length > 0) {
      setSelectedFile(availableFiles[0]);
    }
  }, [availableFiles, selectedFile]);

  // Fetch selected file content
  const { data: fileContent, isLoading: contentLoading } = useQuery({
    queryKey: ['logfile-content', projectId, dirName, selectedFile],
    queryFn: () =>
      pipelineApi
        .getLogFileContent(projectId, `${dirName}/${selectedFile}`)
        .then((r) => r.data),
    enabled: !!projectId && !!selectedFile,
    refetchInterval: pipelineStatus === 'running' ? 3000 : false,
  });

  // Auto-scroll on content update
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [fileContent]);

  const filteredContent = useMemo(() => {
    if (!fileContent?.content) return '';
    if (!searchFilter) return fileContent.content;
    return fileContent.content
      .split('\n')
      .filter((line) => line.toLowerCase().includes(searchFilter.toLowerCase()))
      .join('\n');
  }, [fileContent, searchFilter]);

  const downloadLog = () => {
    if (!fileContent?.content || !selectedFile) return;
    const blob = new Blob([fileContent.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = selectedFile;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (availableFiles.length === 0) {
    return (
      <div className="mt-3 rounded-lg border border-white/[0.06] bg-bg-primary/30 p-6 text-center">
        <FileTextIcon className="w-8 h-8 text-text-muted mx-auto mb-2 opacity-40" />
        <p className="text-sm text-text-muted">No log files available</p>
        <p className="text-[10px] text-text-muted mt-0.5">
          Log files will appear when this milestone runs
        </p>
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-lg border border-white/[0.06] bg-bg-primary/30 overflow-hidden">
      {/* Header with file selector */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/[0.06] bg-bg-secondary/50 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <FileTextIcon className="w-3.5 h-3.5 text-accent-cyan" />
          <span className="text-xs font-medium text-text-primary">Log Files</span>
          {fileContent && (
            <span className="text-[10px] text-text-muted">
              ({(fileContent.size / 1024).toFixed(1)} KB)
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* File selector tabs */}
          <div className="flex items-center gap-0.5 p-0.5 bg-bg-tertiary rounded-md overflow-x-auto max-w-[400px]">
            {availableFiles.map((file) => (
              <button
                key={file}
                onClick={() => setSelectedFile(file)}
                className={clsx(
                  'px-2 py-0.5 text-[10px] rounded transition-colors whitespace-nowrap',
                  selectedFile === file
                    ? 'bg-bg-secondary text-text-primary shadow-sm'
                    : 'text-text-muted hover:text-text-secondary'
                )}
                title={file}
              >
                {file.replace('.log', '')}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative">
            <SearchIcon className="w-3 h-3 text-text-muted absolute left-2 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Filter..."
              className="w-28 pl-6 pr-2 py-1 text-[10px] bg-bg-tertiary rounded border border-border-subtle text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-cyan/50"
            />
          </div>

          {/* Download */}
          <button
            onClick={downloadLog}
            className="p-1 hover:bg-bg-hover rounded transition-colors"
            title="Download log file"
          >
            <DownloadIcon className="w-3.5 h-3.5 text-text-muted" />
          </button>
        </div>
      </div>

      {/* File content */}
      <div
        ref={containerRef}
        className="max-h-[350px] overflow-y-auto p-3 font-mono text-[11px]"
      >
        {contentLoading ? (
          <div className="flex items-center justify-center py-6 text-text-muted">
            <div className="w-4 h-4 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mr-2" />
            Loading...
          </div>
        ) : filteredContent ? (
          <pre className="whitespace-pre-wrap text-text-secondary leading-relaxed">
            {filteredContent}
          </pre>
        ) : (
          <div className="py-6 text-center text-text-muted text-sm">
            Select a log file to view
          </div>
        )}
      </div>
    </div>
  );
}

// ── Combined Log Section (tabs for Event Log vs Log Files) ────────────────────

function CombinedLogSection({
  projectId,
  milestone,
  pipelineStatus,
}: {
  projectId: number;
  milestone: MilestoneInfo;
  pipelineStatus: string;
}) {
  const [logView, setLogView] = useState<'files' | 'events'>('files');

  return (
    <div className="mt-3">
      {/* View toggle */}
      <div className="flex gap-1 mb-1 p-0.5 bg-bg-tertiary rounded-lg w-fit">
        <button
          onClick={() => setLogView('files')}
          className={clsx(
            'px-3 py-1 text-xs rounded-md transition-colors flex items-center gap-1.5',
            logView === 'files'
              ? 'bg-bg-secondary text-text-primary shadow-sm'
              : 'text-text-muted hover:text-text-secondary'
          )}
        >
          <FileTextIcon className="w-3 h-3" />
          Log Files
        </button>
        <button
          onClick={() => setLogView('events')}
          className={clsx(
            'px-3 py-1 text-xs rounded-md transition-colors flex items-center gap-1.5',
            logView === 'events'
              ? 'bg-bg-secondary text-text-primary shadow-sm'
              : 'text-text-muted hover:text-text-secondary'
          )}
        >
          <ScrollTextIcon className="w-3 h-3" />
          Event Log
        </button>
      </div>

      {logView === 'files' ? (
        <LogFileViewer
          projectId={projectId}
          milestone={milestone}
          pipelineStatus={pipelineStatus}
        />
      ) : (
        <MilestoneLogViewer
          projectId={projectId}
          milestone={milestone}
          pipelineStatus={pipelineStatus}
        />
      )}
    </div>
  );
}

// ── Milestone Card ────────────────────────────────────────────────────────────

function MilestoneCard({
  projectId,
  milestone,
  maxBugfixCycles,
  pipelineStatus,
  isExpanded,
  onToggle,
}: {
  projectId: number;
  milestone: MilestoneInfo;
  maxBugfixCycles: number;
  pipelineStatus: string;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const status = getMilestoneStatus(milestone, pipelineStatus);
  const styles = STATUS_STYLES[status];
  const isActive = status === 'active';
  const [selectedCycle, setSelectedCycle] = useState<number | null>(null);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx(
        'rounded-xl border-2 transition-all overflow-hidden',
        styles.border,
        styles.bg,
        isActive && 'shadow-[0_0_20px_rgba(6,182,212,0.15)]'
      )}
    >
      {/* Card header — always visible */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/[0.02] transition-colors"
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {/* Status icon */}
          <StatusIcon status={status} size={20} />

          {/* Name + meta */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-text-primary truncate">
                {milestone.name}
              </span>
              <span className="text-[10px] text-text-muted font-mono">
                M{milestone.id}
              </span>
            </div>
            <div className="flex items-center gap-3 mt-0.5">
              {/* Phase strip */}
              <PhaseStrip milestone={milestone} pipelineStatus={pipelineStatus} />
            </div>
          </div>
        </div>

        {/* Right side: meta + expand icon */}
        <div className="flex items-center gap-3 shrink-0 ml-3">
          {/* Stories count */}
          {milestone.stories > 0 && (
            <span className="text-[10px] text-text-muted">
              {milestone.stories} stories
            </span>
          )}

          {/* Bugfix indicator */}
          {milestone.bugfix_cycle > 0 && (
            <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-status-warning/15 border border-status-warning/30">
              <BugIcon className="w-3 h-3 text-status-warning" />
              <span className="text-[10px] font-semibold text-status-warning">
                {milestone.bugfix_cycle}/{maxBugfixCycles}
              </span>
            </div>
          )}

          {/* Duration */}
          {milestone.started_at && (
            <div className="flex items-center gap-1 text-text-muted">
              <ClockIcon className="w-3 h-3" />
              <span className="text-[10px] font-mono">
                {milestone.completed_at
                  ? formatDuration(milestone.started_at, milestone.completed_at)
                  : 'In progress'}
              </span>
            </div>
          )}

          {/* Status badge */}
          <span
            className={clsx(
              'text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full',
              status === 'completed' && 'bg-status-success/20 text-status-success',
              status === 'active' && 'bg-accent-cyan/20 text-accent-cyan',
              status === 'paused' && 'bg-status-warning/20 text-status-warning',
              status === 'failed' && 'bg-status-error/20 text-status-error',
              status === 'pending' && 'bg-bg-tertiary text-text-muted'
            )}
          >
            {styles.label}
          </span>

          {/* Expand chevron */}
          <motion.div
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            <ChevronDownIcon className="w-4 h-4 text-text-muted" />
          </motion.div>
        </div>
      </button>

      {/* Expanded content */}
      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 border-t border-white/[0.06]">
              {/* FSM visualization */}
              <div className="mt-3">
                <PhaseFSM
                  milestone={milestone}
                  maxBugfixCycles={maxBugfixCycles}
                  pipelineStatus={pipelineStatus}
                  selectedCycle={selectedCycle}
                  onSelectCycle={setSelectedCycle}
                />
              </div>

              {/* Bugfix cycle details */}
              {milestone.bugfix_cycle > 0 && (
                <div className="mt-3 p-3 rounded-lg bg-status-warning/5 border border-status-warning/20">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangleIcon className="w-3.5 h-3.5 text-status-warning" />
                    <span className="text-xs font-semibold text-status-warning">
                      Bugfix Cycles: {milestone.bugfix_cycle} of {maxBugfixCycles}
                    </span>
                  </div>
                  <p className="text-[11px] text-text-muted">
                    QA review detected failures triggering {milestone.bugfix_cycle} bugfix
                    iteration{milestone.bugfix_cycle !== 1 ? 's' : ''}. Ralph was re-invoked in
                    bugfix mode to address failing tests.
                    {milestone.bugfix_cycle >= maxBugfixCycles &&
                      ' Maximum cycles reached — milestone requires manual intervention.'}
                  </p>
                  {/* Cycle dots */}
                  <div className="flex items-center gap-1 mt-2">
                    {Array.from({ length: maxBugfixCycles }, (_, i) => (
                      <div
                        key={i}
                        className={clsx(
                          'w-3 h-3 rounded-full border',
                          i < milestone.bugfix_cycle
                            ? milestone.bugfix_cycle >= maxBugfixCycles
                              ? 'bg-status-error border-status-error/50'
                              : 'bg-status-warning border-status-warning/50'
                            : 'bg-bg-tertiary border-border-subtle'
                        )}
                        title={i < milestone.bugfix_cycle ? `Cycle ${i + 1}` : 'Not used'}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Logs */}
              <CombinedLogSection
                projectId={projectId}
                milestone={milestone}
                pipelineStatus={pipelineStatus}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Duration formatter ────────────────────────────────────────────────────────

function formatDuration(startIso: string, endIso: string): string {
  try {
    const start = new Date(startIso).getTime();
    const end = new Date(endIso).getTime();
    const diffS = Math.round((end - start) / 1000);
    if (diffS < 60) return `${diffS}s`;
    const mins = Math.floor(diffS / 60);
    const secs = diffS % 60;
    if (mins < 60) return `${mins}m ${secs}s`;
    const hours = Math.floor(mins / 60);
    return `${hours}h ${mins % 60}m`;
  } catch {
    return '—';
  }
}

// ── Main Component ────────────────────────────────────────────────────────────

export function PipelineStateView({
  projectId,
  milestones,
  maxBugfixCycles,
  pipelineStatus,
}: PipelineStateViewProps) {
  // Auto-expand the active milestone; all others start collapsed
  const activeMilestone = milestones.find(
    (m) => m.started_at && !m.completed_at && m.phase !== 'pending' && m.phase !== 'failed'
  );

  const [expandedIds, setExpandedIds] = useState<Set<number>>(() => {
    const initial = new Set<number>();
    if (activeMilestone) initial.add(activeMilestone.id);
    return initial;
  });

  // Update expanded when active milestone changes
  useEffect(() => {
    if (activeMilestone) {
      setExpandedIds((prev) => {
        const next = new Set(prev);
        next.add(activeMilestone.id);
        return next;
      });
    }
  }, [activeMilestone?.id]);

  const toggleExpanded = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Summary stats
  const completed = milestones.filter(
    (m) => m.completed_at || m.phase === 'complete'
  ).length;
  const failed = milestones.filter((m) => m.phase === 'failed').length;
  const active = milestones.filter(
    (m) => m.started_at && !m.completed_at && m.phase !== 'pending' && m.phase !== 'failed'
  ).length;
  const pending = milestones.length - completed - failed - active;

  if (milestones.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center">
        <LayersIcon className="w-12 h-12 text-text-muted mb-3" />
        <h3 className="text-lg font-semibold text-text-primary mb-1">
          No Milestones
        </h3>
        <p className="text-text-muted text-sm max-w-md">
          Milestone data will appear here once the pipeline configuration is loaded.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <CheckCircle2Icon className="w-3.5 h-3.5 text-status-success" />
            <span className="text-xs text-text-secondary">
              {completed} complete
            </span>
          </div>
          {active > 0 && (
            <div className="flex items-center gap-1.5">
              <Loader2Icon className="w-3.5 h-3.5 text-accent-cyan animate-spin" />
              <span className="text-xs text-text-secondary">{active} active</span>
            </div>
          )}
          {failed > 0 && (
            <div className="flex items-center gap-1.5">
              <XCircleIcon className="w-3.5 h-3.5 text-status-error" />
              <span className="text-xs text-text-secondary">{failed} failed</span>
            </div>
          )}
          <div className="flex items-center gap-1.5">
            <CircleDotIcon className="w-3.5 h-3.5 text-text-muted" />
            <span className="text-xs text-text-secondary">{pending} pending</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              const allIds = new Set(milestones.map((m) => m.id));
              setExpandedIds((prev) =>
                prev.size === allIds.size ? new Set() : allIds
              );
            }}
            className="text-[10px] text-accent-cyan hover:underline"
          >
            {expandedIds.size === milestones.length ? 'Collapse All' : 'Expand All'}
          </button>
        </div>
      </div>

      {/* Milestone cards */}
      <div className="space-y-3">
        {milestones.map((milestone) => (
          <MilestoneCard
            key={milestone.id}
            projectId={projectId}
            milestone={milestone}
            maxBugfixCycles={maxBugfixCycles}
            pipelineStatus={pipelineStatus}
            isExpanded={expandedIds.has(milestone.id)}
            onToggle={() => toggleExpanded(milestone.id)}
          />
        ))}
      </div>
    </div>
  );
}
