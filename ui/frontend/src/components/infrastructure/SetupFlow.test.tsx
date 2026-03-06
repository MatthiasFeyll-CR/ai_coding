/**
 * Tests for SetupFlow component.
 */
import { projectsApi } from '@/api/client';
import { SetupFlow } from '@/components/infrastructure/SetupFlow';
import { createMockPreCheck, createMockProject, renderWithProviders } from '@/test/helpers';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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

// Mock useWebSocket
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => ({
    connected: true,
    subscribe: vi.fn(() => vi.fn()),
    emit: vi.fn(),
    socket: null,
  }),
}));

describe('SetupFlow', () => {
  const mockProject = createMockProject({
    id: 1,
    name: 'my-test-project',
    root_path: '/home/user/my-test-project',
    status: 'initialized',
    is_setup: false,
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders project name and path', () => {
    (projectsApi.preCheck as any).mockResolvedValue({
      data: createMockPreCheck(),
    });

    renderWithProviders(<SetupFlow project={mockProject} />);

    expect(screen.getByText('my-test-project')).toBeInTheDocument();
    expect(
      screen.getByText('/home/user/my-test-project')
    ).toBeInTheDocument();
  });

  it('shows "Setup Required" badge', () => {
    (projectsApi.preCheck as any).mockResolvedValue({
      data: createMockPreCheck(),
    });

    renderWithProviders(<SetupFlow project={mockProject} />);
    expect(screen.getByText('Setup Required')).toBeInTheDocument();
  });

  it('shows docs structure header', () => {
    (projectsApi.preCheck as any).mockResolvedValue({
      data: createMockPreCheck(),
    });

    renderWithProviders(<SetupFlow project={mockProject} />);
    expect(screen.getByText('Docs Structure')).toBeInTheDocument();
  });

  it('shows Pipeline Configurator section', () => {
    (projectsApi.preCheck as any).mockResolvedValue({
      data: createMockPreCheck(),
    });

    renderWithProviders(<SetupFlow project={mockProject} />);
    expect(screen.getByText('Pipeline Configurator')).toBeInTheDocument();
  });

  it('shows "Run Pipeline Configurator" button', async () => {
    (projectsApi.preCheck as any).mockResolvedValue({
      data: createMockPreCheck(),
    });

    renderWithProviders(<SetupFlow project={mockProject} />);

    await waitFor(() => {
      expect(
        screen.getByText('Run Pipeline Configurator')
      ).toBeInTheDocument();
    });
  });

  it('calls configure API when button is clicked', async () => {
    const user = userEvent.setup();
    (projectsApi.preCheck as any).mockResolvedValue({
      data: createMockPreCheck(),
    });
    (projectsApi.configure as any).mockResolvedValue({
      data: { project_id: 1, status: 'configuring' },
    });

    renderWithProviders(<SetupFlow project={mockProject} />);

    await waitFor(() => {
      expect(
        screen.getByText('Run Pipeline Configurator')
      ).toBeInTheDocument();
    });

    await user.click(screen.getByText('Run Pipeline Configurator'));

    expect(projectsApi.configure).toHaveBeenCalledWith(1);
  });

  it('shows docs structure items after pre-check loads', async () => {
    (projectsApi.preCheck as any).mockResolvedValue({
      data: createMockPreCheck(),
    });

    renderWithProviders(<SetupFlow project={mockProject} />);

    await waitFor(() => {
      expect(screen.getByText('docs/01-requirements')).toBeInTheDocument();
      expect(screen.getByText('docs/02-architecture')).toBeInTheDocument();
    });
  });

  it('shows loading state while scanning', () => {
    // Never resolve the preCheck promise
    (projectsApi.preCheck as any).mockReturnValue(new Promise(() => {}));

    renderWithProviders(<SetupFlow project={mockProject} />);
    expect(screen.getByText('Scanning project…')).toBeInTheDocument();
  });

  it('mentions pipeline-config.json in description', () => {
    (projectsApi.preCheck as any).mockResolvedValue({
      data: createMockPreCheck(),
    });

    renderWithProviders(<SetupFlow project={mockProject} />);
    expect(screen.getByText('pipeline-config.json')).toBeInTheDocument();
  });

  it('shows error on configure failure', async () => {
    const user = userEvent.setup();
    (projectsApi.preCheck as any).mockResolvedValue({
      data: createMockPreCheck(),
    });
    (projectsApi.configure as any).mockRejectedValue({
      response: { data: { error: 'Configuration already in progress' } },
    });

    renderWithProviders(<SetupFlow project={mockProject} />);

    await waitFor(() => {
      expect(
        screen.getByText('Run Pipeline Configurator')
      ).toBeInTheDocument();
    });

    await user.click(screen.getByText('Run Pipeline Configurator'));

    await waitFor(() => {
      expect(
        screen.getByText('Configuration already in progress')
      ).toBeInTheDocument();
    });
  });
});
