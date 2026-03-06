import type {
    ExecutionLog,
    PipelineState,
    PreCheckResult,
    Project,
    StateSnapshot,
    TokenUsage,
} from '@/types';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Projects
export const projectsApi = {
  list: () => api.get<Project[]>('/projects'),
  get: (id: number) => api.get<Project>(`/projects/${id}`),
  create: (data: { project_path: string; name?: string }) =>
    api.post<Project>('/projects', data),
  delete: (id: number) => api.delete(`/projects/${id}`),
  preCheck: (projectPath: string) =>
    api.post<PreCheckResult>('/projects/pre-check', { project_path: projectPath }),
  setup: (projectPath: string) =>
    api.post('/projects/setup', { project_path: projectPath }),
  getConfig: (id: number) => api.get(`/projects/${id}/config`),
  getState: (id: number) => api.get<PipelineState>(`/projects/${id}/state`),
  listSnapshots: (id: number) =>
    api.get<StateSnapshot[]>(`/projects/${id}/snapshots`),
  createSnapshot: (id: number) => api.post(`/projects/${id}/snapshots`),
  restoreSnapshot: (id: number, snapshotId: number) =>
    api.put(`/projects/${id}/restore/${snapshotId}`),
  getModels: (id: number) => api.get<Record<string, string>>(`/projects/${id}/models`),
  updateModels: (id: number, models: Record<string, string>) =>
    api.put(`/projects/${id}/models`, models),
  configure: (id: number) =>
    api.post<{ project_id: number; status: string }>(`/projects/${id}/configure`),
};

// Pipeline control
export const pipelineApi = {
  start: (projectId: number, milestoneId?: number) =>
    api.post(`/pipeline/${projectId}/start`, { milestone_id: milestoneId }),
  stop: (projectId: number) => api.post(`/pipeline/${projectId}/stop`),
  resume: (projectId: number) => api.post(`/pipeline/${projectId}/resume`),
  getLogs: (
    projectId: number,
    params?: { milestone_id?: number; phase?: string; limit?: number }
  ) => api.get<ExecutionLog[]>(`/pipeline/${projectId}/logs`, { params }),
  getTokens: (projectId: number) =>
    api.get<TokenUsage>(`/pipeline/${projectId}/tokens`),
  getMilestones: (projectId: number) =>
    api.get(`/pipeline/${projectId}/milestones`),
};

// Files
export const filesApi = {
  getTree: (projectId: number, path?: string) =>
    api.get(`/files/${projectId}/tree`, { params: path ? { path } : undefined }),
  readFile: (projectId: number, filePath: string) =>
    api.get(`/files/${projectId}/read`, { params: { path: filePath } }),
};

// Models
export const modelsApi = {
  listAvailable: () => api.get<string[]>('/projects/models/available'),
};

// Health
export const healthApi = {
  check: () => api.get('/health'),
  checkRequirements: () => api.post('/requirements/check'),
  getRequirementsStatus: () => api.get('/requirements/status'),
};

export default api;
