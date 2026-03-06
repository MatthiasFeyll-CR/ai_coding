import { useWebSocket } from '@/hooks/useWebSocket';
import type { WebSocketEvents } from '@/types';
import { AnimatePresence, motion } from 'framer-motion';
import { DownloadIcon } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

interface LiveLogsProps {
  projectId?: number;
}

export function LiveLogs({ projectId }: LiveLogsProps) {
  const [logs, setLogs] = useState<
    Array<{ message: string; timestamp: string; level: string }>
  >([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const { subscribe } = useWebSocket(projectId);

  useEffect(() => {
    if (!projectId) return;

    const unsubscribe = subscribe('log', (data: WebSocketEvents['log']) => {
      setLogs((prev) => {
        // Keep last 10,000 lines
        const newLogs = [
          ...prev,
          {
            message: data.message,
            timestamp: data.timestamp,
            level: data.level || 'info',
          },
        ];
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
