/**
 * Tests for the Zustand app store.
 */
import { useAppStore } from '@/store/appStore';
import { createMockProject } from '@/test/helpers';
import { afterEach, describe, expect, it } from 'vitest';

describe('appStore', () => {
  afterEach(() => {
    // Reset store between tests
    useAppStore.setState({
      sidebarCollapsed: false,
      activeProject: null,
      theme: 'dark',
      activeTab: 'state',
      modals: {
        linkProject: false,
        modelSelector: false,
        reinstantiate: false,
        errorDetail: { open: false, error: null },
      },
    });
  });

  it('starts with default state', () => {
    const state = useAppStore.getState();
    expect(state.activeProject).toBeNull();
    expect(state.sidebarCollapsed).toBe(false);
    expect(state.theme).toBe('dark');
    expect(state.activeTab).toBe('state');
  });

  it('can set active project', () => {
    const project = createMockProject({ id: 42, name: 'my-proj' });
    useAppStore.getState().setActiveProject(project);

    expect(useAppStore.getState().activeProject).toEqual(project);
  });

  it('can clear active project', () => {
    useAppStore.getState().setActiveProject(createMockProject());
    useAppStore.getState().setActiveProject(null);

    expect(useAppStore.getState().activeProject).toBeNull();
  });

  it('toggles sidebar', () => {
    expect(useAppStore.getState().sidebarCollapsed).toBe(false);
    useAppStore.getState().toggleSidebar();
    expect(useAppStore.getState().sidebarCollapsed).toBe(true);
    useAppStore.getState().toggleSidebar();
    expect(useAppStore.getState().sidebarCollapsed).toBe(false);
  });

  it('can open and close modals', () => {
    useAppStore.getState().openModal('linkProject');
    expect(useAppStore.getState().modals.linkProject).toBe(true);

    useAppStore.getState().closeModal('linkProject');
    expect(useAppStore.getState().modals.linkProject).toBe(false);
  });

  it('can set active tab', () => {
    useAppStore.getState().setActiveTab('costs');
    expect(useAppStore.getState().activeTab).toBe('costs');
  });

  it('can set error modal', () => {
    const err = { message: 'Something went wrong', code: 500 };
    useAppStore.getState().setError(err);

    const state = useAppStore.getState();
    expect(state.modals.errorDetail.open).toBe(true);
    expect(state.modals.errorDetail.error).toEqual(err);
  });
});
