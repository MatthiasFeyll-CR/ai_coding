import { create } from 'zustand';

export type NotificationType = 'success' | 'error' | 'warning' | 'info';

export interface Notification {
  id: string;
  type: NotificationType;
  message: string;
  timestamp: number;
}

interface NotificationState {
  notifications: Notification[];
  panelOpen: boolean;

  addNotification: (type: NotificationType, message: string) => void;
  removeNotification: (id: string) => void;
  clearAll: () => void;
  togglePanel: () => void;
  closePanel: () => void;
}

let nextId = 1;

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],
  panelOpen: false,

  addNotification: (type, message) =>
    set((state) => ({
      notifications: [
        {
          id: String(nextId++),
          type,
          message,
          timestamp: Date.now(),
        },
        ...state.notifications,
      ],
    })),

  removeNotification: (id) =>
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    })),

  clearAll: () => set({ notifications: [] }),

  togglePanel: () => set((state) => ({ panelOpen: !state.panelOpen })),

  closePanel: () => set({ panelOpen: false }),
}));
