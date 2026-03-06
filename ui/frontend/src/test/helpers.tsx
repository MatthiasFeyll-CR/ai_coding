/**
 * Test utilities & helpers for the frontend test suite.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, type RenderOptions } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';

/**
 * Create a fresh QueryClient for each test (no retries, no cache sharing).
 */
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

/**
 * Custom render that wraps with all providers (Router, QueryClient).
 */
export function renderWithProviders(
  ui: ReactElement,
  options?: RenderOptions & { route?: string; queryClient?: QueryClient }
) {
  const queryClient = options?.queryClient ?? createTestQueryClient();
  const route = options?.route ?? '/';

  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <MemoryRouter initialEntries={[route]}>
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      </MemoryRouter>
    );
  }

  return {
    ...render(ui, { wrapper: Wrapper, ...options }),
    queryClient,
  };
}

/**
 * Factory for a mock project object.
 */
export function createMockProject(overrides: Partial<import('@/types').Project> = {}) {
  return {
    id: 1,
    name: 'test-project',
    root_path: '/home/user/test-project',
    project_path: '/home/user/test-project',
    config_path: '/home/user/test-project/pipeline-config.json',
    status: 'initialized' as const,
    is_setup: false,
    last_run_at: null,
    created_at: '2026-03-06T00:00:00',
    updated_at: '2026-03-06T00:00:00',
    ...overrides,
  };
}

/**
 * Factory for a mock pipeline state.
 */
export function createMockPipelineState(
  overrides: Partial<import('@/types').PipelineState> = {}
) {
  return {
    base_branch: 'main',
    current_milestone: 1,
    current_phase: 'prd_generation',
    status: 'running',
    milestones: {
      '1': {
        id: 1,
        phase: 'prd_generation',
        bugfix_cycle: 0,
        test_fix_cycle: 0,
        started_at: '2026-03-01T00:00:00',
        completed_at: null,
      },
    },
    test_milestone_map: {},
    timestamp: '2026-03-06T12:00:00',
    ...overrides,
  };
}

/**
 * Factory for a mock pre-check result.
 */
export function createMockPreCheck(
  overrides: Partial<import('@/types').PreCheckResult> = {}
) {
  return {
    valid: true,
    docs_structure: {
      'docs/01-requirements': { exists: true, has_handover: true },
      'docs/02-architecture': { exists: true, has_handover: true },
      'docs/03-design': { exists: true, has_handover: false },
      'docs/04-test-architecture': { exists: false, has_handover: false },
      'docs/05-milestones': { exists: true, has_handover: true },
    },
    existing_infrastructure: [],
    project_name: 'test-project',
    ...overrides,
  };
}
