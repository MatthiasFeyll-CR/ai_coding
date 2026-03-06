/**
 * Tests for the API client layer.
 */
import { healthApi, pipelineApi, projectsApi } from '@/api/client';
import axios from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mock axios
vi.mock('axios', () => {
  const mockAxios = {
    create: vi.fn(() => mockAxios),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    defaults: { headers: { common: {} } },
  };
  return { default: mockAxios };
});

describe('projectsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('list() calls GET /api/projects', async () => {
    const mockData = [{ id: 1, name: 'p1' }];
    (axios as any).get.mockResolvedValue({ data: mockData });

    await projectsApi.list();
    expect((axios as any).get).toHaveBeenCalledWith('/projects');
  });

  it('create() calls POST /api/projects', async () => {
    (axios as any).post.mockResolvedValue({ data: { id: 1 } });

    await projectsApi.create({ project_path: '/tmp/test' });
    expect((axios as any).post).toHaveBeenCalledWith('/projects', {
      project_path: '/tmp/test',
    });
  });

  it('create() with name calls POST /api/projects', async () => {
    (axios as any).post.mockResolvedValue({ data: { id: 1 } });

    await projectsApi.create({ project_path: '/tmp/test', name: 'My Project' });
    expect((axios as any).post).toHaveBeenCalledWith('/projects', {
      project_path: '/tmp/test',
      name: 'My Project',
    });
  });

  it('delete() calls DELETE /api/projects/<id>', async () => {
    (axios as any).delete.mockResolvedValue({ data: { success: true } });

    await projectsApi.delete(5);
    expect((axios as any).delete).toHaveBeenCalledWith('/projects/5');
  });

  it('preCheck() calls POST /api/projects/pre-check', async () => {
    (axios as any).post.mockResolvedValue({ data: { valid: true } });

    await projectsApi.preCheck('/tmp/project');
    expect((axios as any).post).toHaveBeenCalledWith('/projects/pre-check', {
      project_path: '/tmp/project',
    });
  });

  it('configure() calls POST /api/projects/<id>/configure', async () => {
    (axios as any).post.mockResolvedValue({
      data: { project_id: 1, status: 'configuring' },
    });

    await projectsApi.configure(1);
    expect((axios as any).post).toHaveBeenCalledWith('/projects/1/configure');
  });

  it('getConfig() calls GET /api/projects/<id>/config', async () => {
    (axios as any).get.mockResolvedValue({ data: {} });

    await projectsApi.getConfig(3);
    expect((axios as any).get).toHaveBeenCalledWith('/projects/3/config');
  });

  it('getState() calls GET /api/projects/<id>/state', async () => {
    (axios as any).get.mockResolvedValue({ data: {} });

    await projectsApi.getState(2);
    expect((axios as any).get).toHaveBeenCalledWith('/projects/2/state');
  });

  it('getModels() calls GET /api/projects/<id>/models', async () => {
    (axios as any).get.mockResolvedValue({ data: {} });

    await projectsApi.getModels(1);
    expect((axios as any).get).toHaveBeenCalledWith('/projects/1/models');
  });

  it('updateModels() calls PUT /api/projects/<id>/models', async () => {
    (axios as any).put.mockResolvedValue({ data: { success: true } });

    await projectsApi.updateModels(1, { prd: 'claude-opus-4' });
    expect((axios as any).put).toHaveBeenCalledWith('/projects/1/models', {
      prd: 'claude-opus-4',
    });
  });

  it('listSnapshots() calls GET /api/projects/<id>/snapshots', async () => {
    (axios as any).get.mockResolvedValue({ data: [] });

    await projectsApi.listSnapshots(1);
    expect((axios as any).get).toHaveBeenCalledWith('/projects/1/snapshots');
  });

  it('createSnapshot() calls POST /api/projects/<id>/snapshots', async () => {
    (axios as any).post.mockResolvedValue({ data: {} });

    await projectsApi.createSnapshot(1);
    expect((axios as any).post).toHaveBeenCalledWith('/projects/1/snapshots');
  });
});

describe('pipelineApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('start() calls POST /api/pipeline/<id>/start', async () => {
    (axios as any).post.mockResolvedValue({ data: { success: true } });

    await pipelineApi.start(1);
    expect((axios as any).post).toHaveBeenCalledWith('/pipeline/1/start', {
      milestone_id: undefined,
    });
  });

  it('start() with milestone calls POST /api/pipeline/<id>/start', async () => {
    (axios as any).post.mockResolvedValue({ data: { success: true } });

    await pipelineApi.start(1, 3);
    expect((axios as any).post).toHaveBeenCalledWith('/pipeline/1/start', {
      milestone_id: 3,
    });
  });

  it('stop() calls POST /api/pipeline/<id>/stop', async () => {
    (axios as any).post.mockResolvedValue({ data: { success: true } });

    await pipelineApi.stop(1);
    expect((axios as any).post).toHaveBeenCalledWith('/pipeline/1/stop');
  });

  it('resume() calls POST /api/pipeline/<id>/resume', async () => {
    (axios as any).post.mockResolvedValue({ data: { success: true } });

    await pipelineApi.resume(1);
    expect((axios as any).post).toHaveBeenCalledWith('/pipeline/1/resume');
  });

  it('getLogs() calls GET /api/pipeline/<id>/logs with params', async () => {
    (axios as any).get.mockResolvedValue({ data: [] });

    await pipelineApi.getLogs(1, { milestone_id: 2, limit: 50 });
    expect((axios as any).get).toHaveBeenCalledWith('/pipeline/1/logs', {
      params: { milestone_id: 2, limit: 50 },
    });
  });

  it('getTokens() calls GET /api/pipeline/<id>/tokens', async () => {
    (axios as any).get.mockResolvedValue({ data: {} });

    await pipelineApi.getTokens(1);
    expect((axios as any).get).toHaveBeenCalledWith('/pipeline/1/tokens');
  });

  it('getMilestones() calls GET /api/pipeline/<id>/milestones', async () => {
    (axios as any).get.mockResolvedValue({ data: [] });

    await pipelineApi.getMilestones(1);
    expect((axios as any).get).toHaveBeenCalledWith('/pipeline/1/milestones');
  });
});

describe('healthApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('check() calls GET /api/health', async () => {
    (axios as any).get.mockResolvedValue({
      data: { status: 'ok' },
    });

    await healthApi.check();
    expect((axios as any).get).toHaveBeenCalledWith('/health');
  });

  it('checkRequirements() calls POST /api/requirements/check', async () => {
    (axios as any).post.mockResolvedValue({ data: {} });

    await healthApi.checkRequirements();
    expect((axios as any).post).toHaveBeenCalledWith('/requirements/check');
  });
});
