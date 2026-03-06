import { pipelineApi } from '@/api/client';
import { PhaseFlow } from '@/components/pipeline/PhaseFlow';
import { useWebSocket } from '@/hooks/useWebSocket';
import type { ExecutionLog, MilestoneInfo, WebSocketEvents } from '@/types';
import { useQuery } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import { DownloadIcon, GitBranchIcon, ScrollTextIcon } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

interface MilestoneDetailProps {
  projectId: number;
  milestone: MilestoneInfo;
  maxBugfixCycles: number;
  pipelineStatus: string;
}

export function MilestoneDetail({
  projectId,
  milestone,
  maxBugfixCycles,
  pipelineStatus,
}: MilestoneDetailProps) {
  const [selectedCycle, setSelectedCycle] = useState<number | null>(null);
  const [liveLogs, setLiveLogs] = useState<
    Array<{ message: string; timestamp: string; level: string }>
  >([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const { subscribe } = useWebSocket(projectId);

  // Fetch historical logs for this milestone
  const { data: historicalLogs } = useQuery({
    queryKey: ['milestone-logs', projectId, milestone.id],
    queryFn: () =>
      pipelineApi
        .getLogs(projectId, { milestone_id: milestone.id, limit: 2000 })
        .then((res) => res.data),
    enabled: !!projectId && !!milestone.id,
    refetchInterval: pipelineStatus === 'running' ? 10000 : false,
  });

  // Subscribe to live WebSocket logs for this milestone
  useEffect(() => {
    if (!projectId) return;

    const unsubscribe = subscribe('log', (data: WebSocketEvents['log']) => {
      // Only capture logs for the current milestone
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

  // Merge historical + live logs, deduplicate
  const allLogs = (() => {
    const historical = (historicalLogs || []).map((log: ExecutionLog) => ({
      message: log.message,
      timestamp: log.created_at,
      level: log.log_level,
    }));

    // Reverse historical so oldest is first (API returns desc)
    const reversed = [...historical].reverse();

    // Merge — live logs created after the last historical log
    const lastHistoricalTs = reversed.length > 0 ? reversed[reversed.length - 1].timestamp : '';
    const newLive = liveLogs.filter((l) => l.timestamp > lastHistoricalTs);

    return [...reversed, ...newLive];
  })();

  const downloadLogs = () => {
    const content = allLogs
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

  return (
    <div className="flex flex-col h-full">
      {/* Phase Progress section */}
      <div className="flex-shrink-0">
        <div className="section-header">
          <GitBranchIcon className="w-4 h-4 text-accent-cyan" />
          <h3>
            {milestone.name}
            <span className="section-subtitle ml-2">— Phase Progress</span>
          </h3>
        </div>
        <div className="px-2 pt-2">
          <PhaseFlow
            milestone={milestone}
            maxBugfixCycles={maxBugfixCycles}
            pipelineStatus={pipelineStatus}
            selectedCycle={selectedCycle}
            onSelectCycle={setSelectedCycle}
          />
        </div>
      </div>

      {/* Visual separator — gradient divider with blur */}
      <div className="relative mx-4 my-3">
        <div className="h-px bg-gradient-to-r from-accent-green/30 via-accent-cyan/20 to-accent-violet/30" />
        <div className="absolute -top-2 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-[10px] tracking-wider uppercase text-text-muted bg-bg-secondary/90 backdrop-blur-sm border border-white/[0.06]">
          output
        </div>
      </div>

      {/* Logs section */}
      <div className="flex-1 flex flex-col min-h-0 mx-3 mb-3 rounded-lg border border-white/[0.06] bg-bg-primary/30 backdrop-blur-xl overflow-hidden">
        <div className="section-header">
          <ScrollTextIcon className="w-4 h-4 text-accent-violet" />
          <h3>Execution Logs</h3>
          <div className="ml-auto">
            <button
              onClick={downloadLogs}
              className="flex items-center gap-1.5 px-2.5 py-1 bg-bg-tertiary/80 hover:bg-bg-hover rounded-md text-xs transition-colors border border-white/[0.06]"
            >
              <DownloadIcon className="w-3 h-3" />
              <span>Download</span>
            </button>
          </div>
        </div>

        <div
          ref={containerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto p-3 font-mono text-xs space-y-0.5"
        >
          {allLogs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-text-muted">
              <p className="text-lg">📄</p>
              <p className="mt-1 text-sm">No logs yet</p>
              <p className="text-xs">Logs will appear when this milestone runs</p>
            </div>
          ) : (
            <AnimatePresence initial={false}>
              {allLogs.map((log, index) => (
                <motion.div
                  key={`${log.timestamp}-${index}`}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.1 }}
                  className={levelColor[log.level] || 'text-text-secondary'}
                >
                  <span className="text-text-muted">
                    [{new Date(log.timestamp).toLocaleTimeString()}]
                  </span>{' '}
                  {log.message}
                </motion.div>
              ))}
            </AnimatePresence>
          )}
        </div>

        {!autoScroll && (
          <div className="px-3 py-1 bg-bg-tertiary text-center border-t border-border-subtle">
            <button
              onClick={() => setAutoScroll(true)}
              className="text-xs text-accent-cyan hover:underline"
            >
              Resume auto-scroll
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
