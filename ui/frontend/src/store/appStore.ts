import type { Project } from '@/types';
import { create } from 'zustand';

type ActiveTab = 'setup' | 'state' | 'git' | 'costs' | 'tests';

interface AppState {
  // UI State
  sidebarCollapsed: boolean;
  activeProject: Project | null;
  theme: 'dark' | 'light';
  activeTab: ActiveTab;

  // Modal State
  modals: {
    linkProject: boolean;
    modelSelector: boolean;
    reinstantiate: boolean;
    errorDetail: {
      open: boolean;
      error: any;
    };
  };

  // Actions
  toggleSidebar: () => void;
  setActiveProject: (project: Project | null) => void;
  setTheme: (theme: 'dark' | 'light') => void;
  setActiveTab: (tab: ActiveTab) => void;
  openModal: (name: string) => void;
  closeModal: (name: string) => void;
  setError: (error: any) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Initial state
  sidebarCollapsed: false,
  activeProject: null,
  theme: 'dark',
  activeTab: 'state',
  modals: {
    linkProject: false,
    modelSelector: false,
    reinstantiate: false,
    errorDetail: {
      open: false,
      error: null,
    },
  },

  // Actions
  toggleSidebar: () =>
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

  setActiveProject: (project) => set({ activeProject: project }),

  setTheme: (theme) => {
    set({ theme });
    if (typeof document !== 'undefined') {
      document.documentElement.classList.toggle('dark', theme === 'dark');
      localStorage.setItem('theme', theme);
    }
  },

  setActiveTab: (tab) => set({ activeTab: tab }),

  openModal: (name) =>
    set((state) => ({
      modals: {
        ...state.modals,
        [name]:
          typeof (state.modals as any)[name] === 'object'
            ? { ...(state.modals as any)[name], open: true }
            : true,
      },
    })),

  closeModal: (name) =>
    set((state) => ({
      modals: {
        ...state.modals,
        [name]:
          typeof (state.modals as any)[name] === 'object'
            ? { ...(state.modals as any)[name], open: false }
            : false,
      },
    })),

  setError: (error) =>
    set((state) => ({
      modals: {
        ...state.modals,
        errorDetail: { open: true, error },
      },
    })),
}));

// Initialize theme from localStorage
if (typeof window !== 'undefined') {
  const savedTheme = localStorage.getItem('theme') as 'dark' | 'light' | null;
  if (savedTheme) {
    useAppStore.getState().setTheme(savedTheme);
  } else {
    useAppStore.getState().setTheme('dark');
  }
}
