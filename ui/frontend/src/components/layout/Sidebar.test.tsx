/**
 * Integration tests for the Sidebar component.
 */
import { projectsApi } from '@/api/client';
import { Sidebar } from '@/components/layout/Sidebar';
import { useAppStore } from '@/store/appStore';
import { createMockProject, renderWithProviders } from '@/test/helpers';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mock the API
vi.mock('@/api/client', () => ({
  projectsApi: {
    list: vi.fn(),
    create: vi.fn(),
    preCheck: vi.fn(),
    setup: vi.fn(),
    get: vi.fn(),
    delete: vi.fn(),
    getConfig: vi.fn(),
    getState: vi.fn(),
    listSnapshots: vi.fn(),
    createSnapshot: vi.fn(),
    restoreSnapshot: vi.fn(),
    getModels: vi.fn(),
    updateModels: vi.fn(),
    configure: vi.fn(),
  },
  pipelineApi: {},
  filesApi: {},
  modelsApi: {},
  healthApi: {},
}));

describe('Sidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    useAppStore.setState({
      sidebarCollapsed: false,
      activeProject: null,
    });
  });

  it('renders header', async () => {
    (projectsApi.list as any).mockResolvedValue({ data: [] });

    renderWithProviders(<Sidebar />);
    expect(screen.getByText('Pipeline Executor')).toBeInTheDocument();
  });

  it('shows "No projects yet" when empty', async () => {
    (projectsApi.list as any).mockResolvedValue({ data: [] });

    renderWithProviders(<Sidebar />);

    await waitFor(() => {
      expect(screen.getByText('No projects yet')).toBeInTheDocument();
    });
  });

  it('lists projects from API', async () => {
    const projects = [
      createMockProject({ id: 1, name: 'Project Alpha' }),
      createMockProject({ id: 2, name: 'Project Beta' }),
    ];
    (projectsApi.list as any).mockResolvedValue({ data: projects });

    renderWithProviders(<Sidebar />);

    await waitFor(() => {
      expect(screen.getByText('Project Alpha')).toBeInTheDocument();
      expect(screen.getByText('Project Beta')).toBeInTheDocument();
    });
  });

  it('clicking a project sets it as active', async () => {
    const user = userEvent.setup();
    const project = createMockProject({ id: 5, name: 'Clickable' });
    (projectsApi.list as any).mockResolvedValue({ data: [project] });

    renderWithProviders(<Sidebar />);

    await waitFor(() => {
      expect(screen.getByText('Clickable')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Clickable'));
    expect(useAppStore.getState().activeProject?.id).toBe(5);
  });

  it('has add project button', async () => {
    (projectsApi.list as any).mockResolvedValue({ data: [] });

    renderWithProviders(<Sidebar />);

    await waitFor(() => {
      expect(screen.getByTitle('Add Project')).toBeInTheDocument();
    });
  });

  it('clicking add project opens link modal', async () => {
    const user = userEvent.setup();
    (projectsApi.list as any).mockResolvedValue({ data: [] });

    renderWithProviders(<Sidebar />);

    await waitFor(() => {
      expect(screen.getByTitle('Add Project')).toBeInTheDocument();
    });

    await user.click(screen.getByTitle('Add Project'));
    expect(useAppStore.getState().modals.linkProject).toBe(true);
  });
});
