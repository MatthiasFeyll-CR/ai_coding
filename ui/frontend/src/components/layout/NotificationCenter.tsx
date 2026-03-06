import type { NotificationType } from '@/store/notificationStore';
import { useNotificationStore } from '@/store/notificationStore';
import { formatDistanceToNow } from 'date-fns';
import {
    AlertTriangleIcon,
    BellIcon,
    CheckCircleIcon,
    InfoIcon,
    Trash2Icon,
    XCircleIcon,
    XIcon,
} from 'lucide-react';
import { useEffect, useRef } from 'react';

const typeConfig: Record<
  NotificationType,
  { icon: typeof CheckCircleIcon; color: string; bg: string }
> = {
  success: {
    icon: CheckCircleIcon,
    color: 'text-status-success',
    bg: 'bg-status-success/10',
  },
  error: {
    icon: XCircleIcon,
    color: 'text-status-error',
    bg: 'bg-status-error/10',
  },
  warning: {
    icon: AlertTriangleIcon,
    color: 'text-status-warning',
    bg: 'bg-status-warning/10',
  },
  info: {
    icon: InfoIcon,
    color: 'text-accent-cyan',
    bg: 'bg-accent-cyan/10',
  },
};

export function NotificationCenter() {
  const { notifications, panelOpen, togglePanel, closePanel, removeNotification, clearAll } =
    useNotificationStore();
  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const count = notifications.length;

  // Close panel on outside click
  useEffect(() => {
    if (!panelOpen) return;

    function handleClick(e: MouseEvent) {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        closePanel();
      }
    }

    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [panelOpen, closePanel]);

  return (
    <div className="relative">
      {/* Bell button */}
      <button
        ref={buttonRef}
        onClick={togglePanel}
        className="relative p-2 hover:bg-bg-hover rounded-lg transition-colors"
        aria-label={`Notifications${count > 0 ? ` (${count})` : ''}`}
      >
        <BellIcon className="w-5 h-5" />
        {count > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] flex items-center justify-center px-1 text-[10px] font-bold leading-none text-white bg-status-error rounded-full">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>

      {/* Floating panel */}
      {panelOpen && (
        <div
          ref={panelRef}
          className="absolute right-0 top-full mt-2 w-96 max-h-[480px] bg-bg-secondary border border-border-subtle rounded-lg shadow-xl z-50 flex flex-col overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
            <h3 className="text-sm font-semibold">Notifications</h3>
            <div className="flex items-center space-x-2">
              {count > 0 && (
                <button
                  onClick={clearAll}
                  className="text-xs text-text-muted hover:text-text-primary transition-colors"
                >
                  Clear all
                </button>
              )}
              <button
                onClick={closePanel}
                className="p-1 hover:bg-bg-hover rounded transition-colors"
              >
                <XIcon className="w-4 h-4 text-text-muted" />
              </button>
            </div>
          </div>

          {/* Notification list */}
          <div className="flex-1 overflow-y-auto">
            {count === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-text-muted">
                <BellIcon className="w-8 h-8 mb-2 opacity-40" />
                <p className="text-sm">No notifications</p>
              </div>
            ) : (
              <ul>
                {notifications.map((n) => {
                  const config = typeConfig[n.type];
                  const Icon = config.icon;
                  return (
                    <li
                      key={n.id}
                      className={`flex items-start gap-3 px-4 py-3 border-b border-border-subtle last:border-b-0 hover:bg-bg-tertiary/50 transition-colors ${config.bg}`}
                    >
                      <Icon className={`w-5 h-5 mt-0.5 shrink-0 ${config.color}`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm leading-snug break-words">{n.message}</p>
                        <p className="text-xs text-text-muted mt-1">
                          {formatDistanceToNow(n.timestamp, { addSuffix: true })}
                        </p>
                      </div>
                      <button
                        onClick={() => removeNotification(n.id)}
                        className="p-1 shrink-0 hover:bg-bg-hover rounded transition-colors"
                        aria-label="Dismiss notification"
                      >
                        <Trash2Icon className="w-4 h-4 text-text-muted hover:text-status-error" />
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
