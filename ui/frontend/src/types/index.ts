export interface Project {
  id: number;
  name: string;
  root_path: string;
  project_path: string;
  config_path: string;
  status: 'initialized' | 'ready' | 'running' | 'error' | 'success' | 'paused' | 'configuring';
  is_setup: boolean;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PipelineState {
  base_branch: string;
  current_milestone: number;
  current_phase: string;
  status: string;
  milestone_progress?: Record<string, number>;
  milestones: Record<string, MilestoneState>;
  test_milestone_map: Record<string, number>;
  git_branch?: string;
  git_log?: string[];
  test_results?: Array<{
    name: string;
    passed: boolean;
    duration: number;
    milestone: string;
  }>;
  timestamp: string;
}

export interface MilestoneState {
  id: number;
  phase: string;
  bugfix_cycle: number;
  test_fix_cycle: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface MilestoneInfo extends MilestoneState {
  name: string;
  slug: string;
  stories: number;
  dependencies: number[];
}

export interface MilestonesResponse {
  milestones: MilestoneInfo[];
  max_bugfix_cycles: number;
}

export interface ExecutionLog {
  id: number;
  project_id: number;
  milestone_id: number | null;
  phase: string | null;
  log_level: 'debug' | 'info' | 'warning' | 'error';
  message: string;
  created_at: string;
}

export interface TokenUsage {
  total: {
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
  };
  by_milestone: Record<
    number,
    {
      input_tokens: number;
      output_tokens: number;
      cost_usd: number;
    }
  >;
  history: Array<{
    id: number;
    project_id: number;
    milestone_id: number | null;
    phase: string | null;
    model: string;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
    created_at: string;
  }>;
}

export interface StateSnapshot {
  id: number;
  project_id: number;
  milestone_id: number | null;
  phase: string | null;
  state_json: string;
  snapshot_type: 'auto' | 'manual' | 'success';
  created_at: string;
}

export interface ValidationReport {
  status: 'passed' | 'failed';
  duration_seconds: number;
  steps: Array<{
    name: string;
    command?: string;
    status: 'passed' | 'failed' | 'warning';
    duration?: number;
    output?: string;
    error?: string;
    expected?: string;
    actual?: string;
    fix_suggestion?: string;
  }>;
  summary: {
    total: number;
    passed: number;
    failed: number;
    warnings: number;
  };
}

export interface PreCheckResult {
  valid: boolean;
  docs_structure: Record<
    string,
    {
      exists: boolean;
      has_handover: boolean;
    }
  >;
  existing_infrastructure: Array<{
    file: string;
    size: number;
    modified: number;
  }>;
  project_name: string;
}

export interface WebSocketEvents {
  log: {
    project_id: number;
    milestone_id?: number;
    phase?: string;
    timestamp: string;
    message: string;
    level?: 'info' | 'warning' | 'error';
  };
  state_change: {
    project_id: number;
    milestone_id?: number;
    old_phase?: string;
    new_phase?: string;
    state: PipelineState;
  };
  token_update: {
    project_id: number;
    milestone_id: number;
    phase: string;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
  };
  status: {
    project_id: number;
    status: string;
    message: string;
  };
  setup_progress: {
    step: string;
    status: string;
    message: string;
    type?: 'progress' | 'assistant' | 'assistant_delta' | 'tool_use' | 'result' | 'error' | 'info' | 'output';
    timestamp?: string;
  };
  cancel_ack: {
    project_id: number;
    status: 'ok' | 'not_found';
    message: string;
  };
}
