import { useConnectionStatus } from '@/hooks/useConnectionStatus';
import { notify } from '@/lib/notify';
import { useEffect, useRef } from 'react';

export function ConnectionIndicator() {
  const { isConnected } = useConnectionStatus();
  const prevConnected = useRef<boolean | null>(null);
  const hasDisconnected = useRef(false);

  useEffect(() => {
    // Skip the very first render (initial mount)
    if (prevConnected.current === null) {
      prevConnected.current = isConnected;
      return;
    }

    // Only fire when the value actually changes
    if (isConnected !== prevConnected.current) {
      if (!isConnected) {
        hasDisconnected.current = true;
        notify('error', 'Connection lost — backend unreachable');
      } else if (hasDisconnected.current) {
        // Only notify reconnection if there was a prior disconnect
        notify('success', 'Connection re-established');
      }
      prevConnected.current = isConnected;
    }
  }, [isConnected]);

  return (
    <div className="flex items-center space-x-2 text-sm">
      <span
        className={`w-2.5 h-2.5 rounded-full ${
          isConnected
            ? 'bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.6)]'
            : 'bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.6)]'
        }`}
      />
      <span className={isConnected ? 'text-green-400' : 'text-red-400'}>
        {isConnected ? 'Connected' : 'Disconnected'}
      </span>
    </div>
  );
}
