/**
 * Tests for LinkProjectModal component.
 */
import { projectsApi } from '@/api/client';
import { LinkProjectModal } from '@/components/modals/LinkProjectModal';
import { useAppStore } from '@/store/appStore';
import { renderWithProviders } from '@/test/helpers';
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

describe('LinkProjectModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Open the modal
    useAppStore.setState({
      modals: {
        linkProject: true,
        modelSelector: false,
        reinstantiate: false,
        errorDetail: { open: false, error: null },
      },
    });
  });

  afterEach(() => {
    useAppStore.setState({
      modals: {
        linkProject: false,
        modelSelector: false,
        reinstantiate: false,
        errorDetail: { open: false, error: null },
      },
    });
  });

  it('renders when modal is open', () => {
    renderWithProviders(<LinkProjectModal />);
    expect(screen.getByRole('heading', { name: 'Link Project' })).toBeInTheDocument();
  });

  it('does not render when modal is closed', () => {
    useAppStore.setState({
      modals: {
        linkProject: false,
        modelSelector: false,
        reinstantiate: false,
        errorDetail: { open: false, error: null },
      },
    });

    renderWithProviders(<LinkProjectModal />);
    expect(screen.queryByText('Link Project')).not.toBeInTheDocument();
  });

  it('has project path input', () => {
    renderWithProviders(<LinkProjectModal />);
    expect(screen.getByPlaceholderText('/path/to/your/project')).toBeInTheDocument();
  });

  it('has optional name input', () => {
    renderWithProviders(<LinkProjectModal />);
    expect(
      screen.getByPlaceholderText('Auto-detected from path')
    ).toBeInTheDocument();
  });

  it('link button is disabled when path is empty', () => {
    renderWithProviders(<LinkProjectModal />);
    const linkButtons = screen.getAllByRole('button');
    const linkBtn = linkButtons.find((b) => b.textContent === 'Link Project');
    expect(linkBtn).toBeDisabled();
  });

  it('link button is enabled when path is entered', async () => {
    const user = userEvent.setup();
    renderWithProviders(<LinkProjectModal />);

    const input = screen.getByPlaceholderText('/path/to/your/project');
    await user.type(input, '/tmp/my-project');

    const linkButtons = screen.getAllByRole('button');
    const linkBtn = linkButtons.find((b) => b.textContent === 'Link Project');
    expect(linkBtn).not.toBeDisabled();
  });

  it('calls create API when link button is clicked', async () => {
    const user = userEvent.setup();
    (projectsApi.create as any).mockResolvedValue({
      data: { id: 1, name: 'test', status: 'initialized' },
    });

    renderWithProviders(<LinkProjectModal />);

    const input = screen.getByPlaceholderText('/path/to/your/project');
    await user.type(input, '/tmp/my-project');

    const linkButtons = screen.getAllByRole('button');
    const linkBtn = linkButtons.find((b) => b.textContent === 'Link Project')!;
    await user.click(linkBtn);

    expect(projectsApi.create).toHaveBeenCalledWith({
      project_path: '/tmp/my-project',
      name: undefined,
    });
  });

  it('passes custom name when provided', async () => {
    const user = userEvent.setup();
    (projectsApi.create as any).mockResolvedValue({
      data: { id: 1, name: 'Custom Name' },
    });

    renderWithProviders(<LinkProjectModal />);

    await user.type(
      screen.getByPlaceholderText('/path/to/your/project'),
      '/tmp/proj'
    );
    await user.type(
      screen.getByPlaceholderText('Auto-detected from path'),
      'Custom Name'
    );

    const linkButtons = screen.getAllByRole('button');
    const linkBtn = linkButtons.find((b) => b.textContent === 'Link Project')!;
    await user.click(linkBtn);

    expect(projectsApi.create).toHaveBeenCalledWith({
      project_path: '/tmp/proj',
      name: 'Custom Name',
    });
  });

  it('shows error message on API failure', async () => {
    const user = userEvent.setup();
    (projectsApi.create as any).mockRejectedValue({
      response: { data: { error: 'Project path does not exist' } },
    });

    renderWithProviders(<LinkProjectModal />);

    await user.type(
      screen.getByPlaceholderText('/path/to/your/project'),
      '/invalid/path'
    );

    const linkButtons = screen.getAllByRole('button');
    const linkBtn = linkButtons.find((b) => b.textContent === 'Link Project')!;
    await user.click(linkBtn);

    await waitFor(() => {
      expect(screen.getByText('Project path does not exist')).toBeInTheDocument();
    });
  });

  it('closes modal via cancel button', async () => {
    const user = userEvent.setup();
    renderWithProviders(<LinkProjectModal />);

    const cancelBtn = screen.getByRole('button', { name: 'Cancel' });
    await user.click(cancelBtn);

    expect(useAppStore.getState().modals.linkProject).toBe(false);
  });
});
