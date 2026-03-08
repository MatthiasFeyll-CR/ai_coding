export interface Project {
  id: number;
  name: string;
  root_path: string;
  project_path: string;
  config_path: string;
  status: 'initialized' | 'ready' | 'running' | 'error' | 'success' | 'paused' | 'configuring' | 'stopped';
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
    cache_creation_tokens: number;
    cache_read_tokens: number;
    cost_usd: number;
    invocations: number;
  };
  by_milestone: Record<
    number,
    {
      input_tokens: number;
      output_tokens: number;
      cache_creation_tokens: number;
      cache_read_tokens: number;
      cost_usd: number;
      invocations: number;
    }
  >;
  by_phase: Record<
    string,
    {
      input_tokens: number;
      output_tokens: number;
      cost_usd: number;
      invocations: number;
    }
  >;
  by_model: Record<
    string,
    {
      input_tokens: number;
      output_tokens: number;
      cost_usd: number;
      invocations: number;
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
    cache_creation_tokens: number;
    cache_read_tokens: number;
    cost_usd: number;
    session_id: string;
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

// ── Test Analytics ──────────────────────────────────────────────────────────

export interface TestAnalyticsSummary {
  total_test_runs: number;
  passed: number;
  failed: number;
  pass_rate: number;
  total_fix_cycles: number;
  total_bugfix_cycles: number;
  total_test_fix_cycles: number;
  avg_duration_s: number;
  total_test_time_s: number;
  qa_pass_count: number;
  qa_fail_count: number;
  qa_first_pass_count: number;
  max_bugfix_cycles: number;
}

export interface MilestoneTestAnalytics {
  id: number;
  name: string;
  phase: string;
  bugfix_cycles: number;
  test_fix_cycles: number;
  test_runs: number;
  tests_passed: number;
  tests_failed: number;
  pass_rate: number;
  total_duration_s: number;
  avg_duration_s: number;
  qa_verdicts: number;
  final_verdict: string;
  first_pass: boolean;
}

export interface EnforcementPoint {
  label: string;
  runs: number;
  passed: number;
  failed: number;
}

export interface TimelineEvent {
  ts: string;
  type: 'test_run' | 'qa_verdict';
  milestone: number;
  cycle: number;
  passed?: boolean;
  duration_s?: number;
  verdict?: string;
}

export interface FailingFile {
  file: string;
  failures: number;
}

export interface QaReport {
  milestone: number;
  cycle: number;
  passed: boolean;
  exit_code: number;
  file: string;
}

export interface TestAnalytics {
  summary: TestAnalyticsSummary;
  milestones: MilestoneTestAnalytics[];
  enforcement_points: EnforcementPoint[];
  timeline: TimelineEvent[];
  top_failing_files: FailingFile[];
  qa_reports: QaReport[];
}
