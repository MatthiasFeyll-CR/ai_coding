/**
 * Integration tests for the DashboardPage.
 *
 * Tests the page-level orchestration: project selection display,
 * setup flow routing, and tab rendering.
 */
import { projectsApi } from '@/api/client';
import { DashboardPage } from '@/pages/DashboardPage';
import { useAppStore } from '@/store/appStore';
import { createMockProject, renderWithProviders } from '@/test/helpers';
import { screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

// Mock the API
vi.mock('@/api/client', () => ({
  projectsApi: {
    create: vi.fn(),
    list: vi.fn(),
    preCheck: vi.fn(),
    setup: vi.fn(),
    get: vi.fn(),
    delete: vi.fn(),
    getConfig: vi.fn(),
    getState: vi.fn().mockResolvedValue({ data: {} }),
    listSnapshots: vi.fn(),
    createSnapshot: vi.fn(),
    restoreSnapshot: vi.fn(),
    getModels: vi.fn(),
    updateModels: vi.fn(),
    configure: vi.fn(),
  },
  pipelineApi: {
    getLogs: vi.fn().mockResolvedValue({ data: [] }),
    getTokens: vi.fn().mockResolvedValue({
      data: {
        total: { input_tokens: 0, output_tokens: 0, cost_usd: 0, cache_creation_tokens: 0, cache_read_tokens: 0, invocations: 0 },
        by_milestone: {},
        by_phase: {},
        by_model: {},
        history: [],
      },
    }),
    getMilestones: vi.fn().mockResolvedValue({ data: { milestones: [], max_bugfix_cycles: 3 } }),
    start: vi.fn(),
    stop: vi.fn(),
    resume: vi.fn(),
  },
  filesApi: {
    getTree: vi.fn().mockResolvedValue({ data: {} }),
    readFile: vi.fn(),
  },
  modelsApi: {
    listAvailable: vi.fn().mockResolvedValue({ data: [] }),
  },
  healthApi: {
    check: vi.fn().mockResolvedValue({ data: { status: 'ok' } }),
    checkRequirements: vi.fn(),
    getRequirementsStatus: vi.fn().mockResolvedValue({ data: [] }),
  },
}));

// Mock useWebSocket
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => ({
    connected: true,
    subscribe: vi.fn(() => vi.fn()),
    emit: vi.fn(),
    socket: null,
  }),
}));

describe('DashboardPage', () => {
  afterEach(() => {
    useAppStore.setState({ activeProject: null });
    vi.clearAllMocks();
  });

  it('shows empty state when no project is selected', () => {
    renderWithProviders(<DashboardPage />, { route: '/dashboard' });
    expect(screen.getByText('No Project Selected')).toBeInTheDocument();
  });

  it('shows Link Project button in empty state', () => {
    renderWithProviders(<DashboardPage />, { route: '/dashboard' });
    expect(
      screen.getByRole('button', { name: 'Link Project' })
    ).toBeInTheDocument();
  });

  it('shows SetupFlow when project is not set up', () => {
    const project = createMockProject({ is_setup: false, status: 'initialized' });
    useAppStore.setState({ activeProject: project });

    (projectsApi.preCheck as any).mockResolvedValue({
      data: {
        valid: true,
        docs_structure: {},
        existing_infrastructure: [],
        project_name: 'test',
      },
    });

    renderWithProviders(<DashboardPage />, { route: '/dashboard' });
    expect(screen.getByText('Setup Required')).toBeInTheDocument();
  });

  it('shows dashboard with project name when set up', async () => {
    const project = createMockProject({
      is_setup: true,
      status: 'ready',
      name: 'my-ready-project',
    });
    useAppStore.setState({ activeProject: project });

    renderWithProviders(<DashboardPage />, { route: '/dashboard' });

    await waitFor(() => {
      expect(screen.getByText('my-ready-project')).toBeInTheDocument();
    });
  });

  it('shows dashboard tabs when project is set up', async () => {
    const project = createMockProject({ is_setup: true, status: 'ready' });
    useAppStore.setState({ activeProject: project });

    renderWithProviders(<DashboardPage />, { route: '/dashboard' });

    await waitFor(() => {
      expect(screen.getByText('Pipeline State')).toBeInTheDocument();
      expect(screen.getByText('Git Operations')).toBeInTheDocument();
      expect(screen.getByText('Cost Tracking')).toBeInTheDocument();
    });
  });
});
