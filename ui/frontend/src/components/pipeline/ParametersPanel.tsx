/**
 * ParametersPanel — editable pipeline configuration parameters.
 *
 * Groups parameters semantically, supports inline editing with auto-save
 * on blur, and provides expandable help text per parameter.
 */

import { projectsApi } from '@/api/client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import clsx from 'clsx';
import { AnimatePresence, motion } from 'framer-motion';
import {
    AlertTriangleIcon,
    CheckCircle2Icon,
    HelpCircleIcon,
    Loader2Icon,
    SettingsIcon,
    SlidersIcon,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

// ── Types ─────────────────────────────────────────────────────────────────────

type FieldType = 'number' | 'text' | 'boolean' | 'command';

interface ParameterDef {
  key: string;           // dot-separated config path, e.g. "qa.max_bugfix_cycles"
  label: string;
  type: FieldType;
  defaultValue: unknown;
  help: string;          // shown on focus/expand
  nonNegative?: boolean; // for number fields
}

interface ParameterGroup {
  id: string;
  title: string;
  icon: React.ReactNode;
  description: string;
  params: ParameterDef[];
}

// ── Parameter definitions ─────────────────────────────────────────────────────

const PARAMETER_GROUPS: ParameterGroup[] = [
  {
    id: 'agent',
    title: 'Agent Execution',
    icon: <SlidersIcon className="w-4 h-4" />,
    description: 'Controls how the AI coding agent executes within each milestone.',
    params: [
      {
        key: 'ralph.max_iterations_multiplier',
        label: 'Max Iterations Multiplier',
        type: 'number',
        defaultValue: 3,
        nonNegative: true,
        help: 'Multiplied by the story count to compute the iteration budget for the agent. Higher values (> 5) allow more AI attempts per milestone but increase cost and runtime. Lower values (1–2) restrict the agent, risking incomplete work. Default 3 is a balanced trade-off.',
      },
      {
        key: 'ralph.stuck_threshold',
        label: 'Stuck Threshold',
        type: 'number',
        defaultValue: 3,
        nonNegative: true,
        help: 'Number of consecutive iterations without measurable progress before the agent is considered stuck and the phase is escalated. Low values (1–2) trigger early exits but may skip solvable problems. High values (> 5) allow more patience but can waste tokens on loops.',
      },
      {
        key: 'ralph.tool',
        label: 'Agent CLI Tool',
        type: 'text',
        defaultValue: 'claude',
        help: 'The CLI command used to invoke the AI agent. Typically "claude". Change only if using a custom wrapper or alternative tool binary.',
      },
    ],
  },
  {
    id: 'qa',
    title: 'Quality Assurance',
    icon: <AlertTriangleIcon className="w-4 h-4" />,
    description: 'Controls bugfix and gate check cycles after implementation.',
    params: [
      {
        key: 'qa.max_bugfix_cycles',
        label: 'Max Bugfix Cycles',
        type: 'number',
        defaultValue: 3,
        nonNegative: true,
        help: 'Maximum times the QA review can fail and trigger a bugfix cycle before escalating. Higher values (> 5) give more chances to fix issues automatically but increase cost. A value of 0 disables the bugfix loop entirely.',
      },
      {
        key: 'gate_checks.max_fix_cycles',
        label: 'Gate Check Max Fix Cycles',
        type: 'number',
        defaultValue: 3,
        nonNegative: true,
        help: 'Maximum fix attempts when gate check commands fail. Gate checks are custom validations (e.g., linting, type-checking) that run after each milestone. Higher values allow more auto-fix attempts.',
      },
    ],
  },
  {
    id: 'testing',
    title: 'Test Execution',
    icon: <SettingsIcon className="w-4 h-4" />,
    description: 'Test commands, timeouts, and infrastructure setup.',
    params: [
      {
        key: 'test_execution.test_command',
        label: 'Test Command',
        type: 'command',
        defaultValue: '',
        help: 'The primary test suite command executed before QA review. Example: "python -m pytest tests/ -q" or "npm test". Leave empty if no tests are defined yet.',
      },
      {
        key: 'test_execution.build_command',
        label: 'Build Command',
        type: 'command',
        defaultValue: null,
        help: 'Command to run before tests (e.g., "npm run build" or "cargo build"). Null or empty means no build step.',
      },
      {
        key: 'test_execution.integration_test_command',
        label: 'Integration Test Command',
        type: 'command',
        defaultValue: null,
        help: 'Separate integration test command rendered in the agent runtime footer. Useful when you have a split test suite (unit vs. integration).',
      },
      {
        key: 'test_execution.timeout_seconds',
        label: 'Test Timeout (s)',
        type: 'number',
        defaultValue: 300,
        nonNegative: true,
        help: 'Maximum seconds before the test command is killed. For large test suites, increase to 600+. Very high values risk hanging processes.',
      },
      {
        key: 'test_execution.build_timeout_seconds',
        label: 'Build Timeout (s)',
        type: 'number',
        defaultValue: 300,
        nonNegative: true,
        help: 'Maximum seconds for the build command. Increase for projects with long compile times (e.g., Rust, large TypeScript projects).',
      },
      {
        key: 'test_execution.max_fix_cycles',
        label: 'Test Fix Max Cycles',
        type: 'number',
        defaultValue: 5,
        nonNegative: true,
        help: 'Maximum attempts to auto-fix test failures. Higher values (> 5) allow more passes but significantly increase cost. A value of 0 means no test-fix attempts.',
      },
      {
        key: 'test_execution.setup_command',
        label: 'Test Setup Command',
        type: 'command',
        defaultValue: null,
        help: 'Start test infrastructure services before tests (e.g., "docker compose up -d"). Runs once per test execution phase.',
      },
      {
        key: 'test_execution.teardown_command',
        label: 'Test Teardown Command',
        type: 'command',
        defaultValue: null,
        help: 'Stop test infrastructure after tests (e.g., "docker compose down"). Runs after test execution completes.',
      },
      {
        key: 'test_execution.setup_timeout_seconds',
        label: 'Setup Timeout (s)',
        type: 'number',
        defaultValue: 120,
        nonNegative: true,
        help: 'Maximum seconds for the setup command to complete. Infrastructure like databases may need 30-60s to start.',
      },
      {
        key: 'test_execution.condition',
        label: 'Test Condition',
        type: 'command',
        defaultValue: '',
        help: 'Shell command that determines whether tests should run. If this exits non-zero, tests are skipped. Example: "test -f package.json" to only run tests when the file exists.',
      },
    ],
  },
  {
    id: 'retry',
    title: 'Retry & Resilience',
    icon: <SlidersIcon className="w-4 h-4" />,
    description: 'How the pipeline handles transient failures and API errors.',
    params: [
      {
        key: 'retry.max_retries',
        label: 'Max Retries',
        type: 'number',
        defaultValue: 3,
        nonNegative: true,
        help: 'Maximum retry attempts for Claude subprocess calls on transient failures (e.g., network errors, rate limits). Each retry waits for the backoff period.',
      },
      {
        key: 'retry.backoff_seconds',
        label: 'Backoff (s)',
        type: 'number',
        defaultValue: 30,
        nonNegative: true,
        help: 'Seconds to wait between retry attempts. Higher values reduce rate limit pressure but slow recovery. Values < 10 may hit rate limits repeatedly.',
      },
    ],
  },
  {
    id: 'cost',
    title: 'Cost Control',
    icon: <SlidersIcon className="w-4 h-4" />,
    description: 'Budget limits and cost warning thresholds.',
    params: [
      {
        key: 'cost.budget_usd',
        label: 'Budget (USD)',
        type: 'number',
        defaultValue: 0,
        nonNegative: true,
        help: 'Total AI spend budget in US dollars. Set to 0 for unlimited. When exceeded, the pipeline stops with a fatal CostBudgetExceeded error. Typical projects use $5–$50 per milestone.',
      },
      {
        key: 'cost.warn_at_pct',
        label: 'Warn At (%)',
        type: 'number',
        defaultValue: 80,
        nonNegative: true,
        help: 'Log a warning when this percentage of the budget is consumed. Useful for early alerts before hitting the hard cap. Set to 100 to only warn at the limit.',
      },
    ],
  },
  {
    id: 'context',
    title: 'Context Limits',
    icon: <SlidersIcon className="w-4 h-4" />,
    description: 'Controls the context bundle size fed to the AI agent.',
    params: [
      {
        key: 'context_limits.max_lines',
        label: 'Max Context Lines',
        type: 'number',
        defaultValue: 3000,
        nonNegative: true,
        help: 'Maximum lines in .ralph/context.md before truncation. Higher values give the agent more context but increase token usage. Values > 5000 may exceed model context windows.',
      },
      {
        key: 'context_limits.max_tokens',
        label: 'Max Context Tokens',
        type: 'number',
        defaultValue: 15000,
        nonNegative: true,
        help: 'Maximum estimated tokens in the context bundle. This is the hard cap used to decide when to truncate sections. Typical range: 10000–20000.',
      },
      {
        key: 'context_limits.warn_pct',
        label: 'Warn At (%)',
        type: 'number',
        defaultValue: 80,
        nonNegative: true,
        help: 'Warning threshold as percentage of max limits. Emits a log warning when context approaches the cap.',
      },
      {
        key: 'context_limits.tokens_per_line',
        label: 'Tokens per Line',
        type: 'number',
        defaultValue: 4.5,
        nonNegative: true,
        help: 'Heuristic multiplier for line-to-token estimation. Most code averages 3–5 tokens per line. Adjust if your code has unusually long or short lines.',
      },
      {
        key: 'context_limits.fix_context_max_lines',
        label: 'Fix Context Max Lines',
        type: 'number',
        defaultValue: 800,
        nonNegative: true,
        help: 'Maximum lines of domain context injected into bugfix prompts. Keeps fix prompts focused. Higher values give more context for complex fixes but may dilute the prompt.',
      },
    ],
  },
  {
    id: 'reconciliation',
    title: 'Reconciliation',
    icon: <SlidersIcon className="w-4 h-4" />,
    description: 'Post-milestone spec reconciliation behavior.',
    params: [
      {
        key: 'reconciliation.blocking',
        label: 'Blocking',
        type: 'boolean',
        defaultValue: true,
        help: 'When enabled, the pipeline refuses to start the next milestone if the previous milestone has unresolved reconciliation debt (failed spec updates). Disable to proceed despite stale specs.',
      },
    ],
  },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  const parts = path.split('.');
  let current: unknown = obj;
  for (const part of parts) {
    if (current == null || typeof current !== 'object') return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

// ── Individual Parameter Field ────────────────────────────────────────────────

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

function ParameterField({
  param,
  currentValue,
  onSave,
}: {
  param: ParameterDef;
  currentValue: unknown;
  onSave: (key: string, value: unknown) => Promise<void>;
}) {
  const displayValue = currentValue ?? param.defaultValue ?? '';
  const [localValue, setLocalValue] = useState(String(displayValue ?? ''));
  const [status, setStatus] = useState<SaveStatus>('idle');
  const [showHelp, setShowHelp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync when external data changes
  useEffect(() => {
    const v = currentValue ?? param.defaultValue ?? '';
    setLocalValue(String(v ?? ''));
  }, [currentValue, param.defaultValue]);

  const validate = useCallback(
    (raw: string): { valid: boolean; parsed: unknown; error?: string } => {
      if (param.type === 'boolean') {
        return { valid: true, parsed: raw === 'true' };
      }
      if (param.type === 'number') {
        if (raw.trim() === '') {
          return { valid: true, parsed: param.defaultValue };
        }
        const num = Number(raw);
        if (isNaN(num)) return { valid: false, parsed: raw, error: 'Must be a number' };
        if (param.nonNegative && num < 0)
          return { valid: false, parsed: raw, error: 'Must be non-negative' };
        // Preserve int vs float
        return { valid: true, parsed: raw.includes('.') ? num : Math.floor(num) };
      }
      if (param.type === 'command' || param.type === 'text') {
        const trimmed = raw.trim();
        return { valid: true, parsed: trimmed || null };
      }
      return { valid: true, parsed: raw };
    },
    [param],
  );

  const handleSave = useCallback(async () => {
    const { valid, parsed, error: validationError } = validate(localValue);
    if (!valid) {
      setError(validationError ?? 'Invalid value');
      setStatus('error');
      return;
    }

    // Don't save if value hasn't changed
    const prev = currentValue ?? param.defaultValue ?? '';
    if (String(parsed ?? '') === String(prev ?? '')) {
      return;
    }

    setStatus('saving');
    setError(null);
    try {
      await onSave(param.key, parsed);
      setStatus('saved');
      clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setStatus('idle'), 2000);
    } catch {
      setStatus('error');
      setError('Failed to save');
    }
  }, [localValue, currentValue, param, validate, onSave]);

  const handleToggle = useCallback(async () => {
    const newVal = !(currentValue ?? param.defaultValue);
    setLocalValue(String(newVal));
    setStatus('saving');
    try {
      await onSave(param.key, newVal);
      setStatus('saved');
      clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setStatus('idle'), 2000);
    } catch {
      setStatus('error');
      setError('Failed to save');
    }
  }, [currentValue, param, onSave]);

  // Cleanup timeout on unmount
  useEffect(() => () => clearTimeout(timeoutRef.current), []);

  const isActive = showHelp;

  return (
    <div
      className={clsx(
        'rounded-lg border transition-colors',
        isActive
          ? 'bg-bg-tertiary/60 border-accent-cyan/30'
          : 'bg-bg-secondary/40 border-border-subtle hover:border-border-emphasis',
      )}
    >
      <div className="p-3 flex items-center gap-3">
        {/* Label + help toggle */}
        <button
          type="button"
          onClick={() => setShowHelp(!showHelp)}
          className="flex-1 min-w-0 text-left group"
        >
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-medium text-text-primary truncate">
              {param.label}
            </span>
            <HelpCircleIcon className={clsx(
              'w-3.5 h-3.5 shrink-0 transition-colors',
              showHelp ? 'text-accent-cyan' : 'text-text-muted group-hover:text-accent-cyan',
            )} />
          </div>
          <span className="text-[10px] text-text-muted font-mono">{param.key}</span>
        </button>

        {/* Input */}
        <div className="flex items-center gap-2 shrink-0">
          {param.type === 'boolean' ? (
            <button
              onClick={handleToggle}
              className={clsx(
                'relative w-10 h-5 rounded-full transition-colors',
                (currentValue ?? param.defaultValue) ? 'bg-accent-cyan' : 'bg-bg-tertiary',
              )}
            >
              <motion.div
                className="absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-md"
                animate={{ left: (currentValue ?? param.defaultValue) ? 22 : 2 }}
                transition={{ type: 'spring', stiffness: 700, damping: 30 }}
              />
            </button>
          ) : (
            <input
              ref={inputRef}
              type={param.type === 'number' ? 'number' : 'text'}
              value={localValue}
              onChange={(e) => {
                setLocalValue(e.target.value);
                setError(null);
                setStatus('idle');
              }}
              onBlur={() => {
                handleSave();
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.currentTarget.blur();
                }
              }}
              min={param.nonNegative ? 0 : undefined}
              step={param.type === 'number' ? 'any' : undefined}
              className={clsx(
                'bg-bg-tertiary border rounded-md px-3 py-1.5 text-sm text-text-primary',
                'focus:outline-none focus:ring-1 focus:ring-accent-cyan focus:border-accent-cyan',
                'transition-colors [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none',
                param.type === 'command' ? 'font-mono w-64' : 'w-28',
                error ? 'border-status-error' : 'border-border-subtle',
              )}
              placeholder={param.type === 'command' ? 'e.g. npm test' : String(param.defaultValue ?? '')}
            />
          )}

          {/* Status indicator */}
          <div className="w-5 h-5 flex items-center justify-center">
            {status === 'saving' && (
              <Loader2Icon className="w-4 h-4 text-accent-cyan animate-spin" />
            )}
            {status === 'saved' && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', stiffness: 500, damping: 25 }}
              >
                <CheckCircle2Icon className="w-4 h-4 text-status-success" />
              </motion.div>
            )}
            {status === 'error' && (
              <AlertTriangleIcon className="w-4 h-4 text-status-error" />
            )}
          </div>
        </div>
      </div>

      {/* Help text — collapses in/out */}
      <AnimatePresence>
        {showHelp && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 pt-0">
              <p className="text-xs text-text-secondary leading-relaxed">
                {param.help}
              </p>
              {error && (
                <p className="text-xs text-status-error mt-1">{error}</p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Group Content (renders params for a single group) ─────────────────────────

function GroupContent({
  group,
  config,
  onSave,
}: {
  group: ParameterGroup;
  config: Record<string, unknown>;
  onSave: (key: string, value: unknown) => Promise<void>;
}) {
  return (
    <div className="space-y-2">
      <div className="mb-3">
        <p className="text-xs text-text-secondary">{group.description}</p>
      </div>
      {group.params.map((param) => (
        <ParameterField
          key={param.key}
          param={param}
          currentValue={getNestedValue(config, param.key)}
          onSave={onSave}
        />
      ))}
    </div>
  );
}

// ── Gate Checks Editor ────────────────────────────────────────────────────────

interface GateCheck {
  name: string;
  command: string;
  condition?: string;
  required?: boolean;
}

function GateChecksEditor({
  checks,
  maxFixCycles,
  onSave,
}: {
  checks: GateCheck[];
  maxFixCycles: number;
  onSave: (key: string, value: unknown) => Promise<void>;
}) {
  const [localChecks, setLocalChecks] = useState<GateCheck[]>(checks);
  const [statuses, setStatuses] = useState<Record<number, SaveStatus>>({});

  useEffect(() => setLocalChecks(checks), [checks]);

  const handleCheckChange = useCallback(
    async (index: number, field: keyof GateCheck, value: string | boolean) => {
      const updated = [...localChecks];
      updated[index] = { ...updated[index], [field]: value };
      setLocalChecks(updated);
    },
    [localChecks],
  );

  const handleCheckBlur = useCallback(
    async (index: number) => {
      setStatuses((s) => ({ ...s, [index]: 'saving' }));
      try {
        await onSave('gate_checks.checks', localChecks);
        setStatuses((s) => ({ ...s, [index]: 'saved' }));
        setTimeout(() => setStatuses((s) => ({ ...s, [index]: 'idle' })), 2000);
      } catch {
        setStatuses((s) => ({ ...s, [index]: 'error' }));
      }
    },
    [localChecks, onSave],
  );

  const addCheck = useCallback(async () => {
    const newCheck: GateCheck = { name: '', command: '', required: true };
    const updated = [...localChecks, newCheck];
    setLocalChecks(updated);
  }, [localChecks]);

  const removeCheck = useCallback(
    async (index: number) => {
      const updated = localChecks.filter((_, i) => i !== index);
      setLocalChecks(updated);
      try {
        await onSave('gate_checks.checks', updated);
      } catch {
        // Restore
        setLocalChecks(localChecks);
      }
    },
    [localChecks, onSave],
  );

  return (
    <div className="rounded-xl border border-border-subtle overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 bg-bg-secondary/70">
        <div className="p-1.5 rounded-md bg-bg-tertiary text-accent-cyan">
          <SettingsIcon className="w-4 h-4" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-text-primary">Gate Checks</h3>
          <p className="text-[10px] text-text-muted">
            Custom validation commands run after each milestone. Failures trigger auto-fix cycles.
          </p>
        </div>
      </div>

      <div className="p-3 space-y-3 bg-bg-primary/30">
        {localChecks.length === 0 && (
          <p className="text-xs text-text-muted text-center py-4">
            No gate checks configured. Add one to enforce custom validations.
          </p>
        )}

        {localChecks.map((check, i) => (
          <div
            key={i}
            className="bg-bg-secondary/40 border border-border-subtle rounded-lg p-3 space-y-2"
          >
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={check.name}
                onChange={(e) => handleCheckChange(i, 'name', e.target.value)}
                onBlur={() => handleCheckBlur(i)}
                placeholder="Check name"
                className="flex-1 bg-bg-tertiary border border-border-subtle rounded-md px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-cyan"
              />
              <div className="w-5 h-5 flex items-center justify-center">
                {statuses[i] === 'saved' && <CheckCircle2Icon className="w-4 h-4 text-status-success" />}
                {statuses[i] === 'saving' && <Loader2Icon className="w-4 h-4 text-accent-cyan animate-spin" />}
              </div>
              <button
                onClick={() => removeCheck(i)}
                className="text-text-muted hover:text-status-error text-xs px-2 py-1 rounded transition-colors"
              >
                Remove
              </button>
            </div>
            <input
              type="text"
              value={check.command}
              onChange={(e) => handleCheckChange(i, 'command', e.target.value)}
              onBlur={() => handleCheckBlur(i)}
              placeholder="Shell command (e.g. npm run lint)"
              className="w-full bg-bg-tertiary border border-border-subtle rounded-md px-3 py-1.5 text-sm font-mono text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-cyan"
            />
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-1.5 text-xs text-text-secondary">
                <input
                  type="checkbox"
                  checked={check.required !== false}
                  onChange={(e) => {
                    handleCheckChange(i, 'required', e.target.checked);
                    setTimeout(() => handleCheckBlur(i), 50);
                  }}
                  className="accent-accent-cyan"
                />
                Required
              </label>
              <input
                type="text"
                value={check.condition || ''}
                onChange={(e) => handleCheckChange(i, 'condition', e.target.value)}
                onBlur={() => handleCheckBlur(i)}
                placeholder="Condition (optional)"
                className="flex-1 bg-bg-tertiary border border-border-subtle rounded-md px-2 py-1 text-xs font-mono text-text-secondary focus:outline-none focus:ring-1 focus:ring-accent-cyan"
              />
            </div>
          </div>
        ))}

        <button
          onClick={addCheck}
          className="w-full py-2 text-xs text-accent-cyan border border-dashed border-accent-cyan/30 rounded-lg hover:bg-accent-cyan/5 transition-colors"
        >
          + Add Gate Check
        </button>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

interface ParametersPanelProps {
  projectId: number;
}

export function ParametersPanel({ projectId }: ParametersPanelProps) {
  const queryClient = useQueryClient();

  const { data: config, isLoading } = useQuery({
    queryKey: ['project-config', projectId],
    queryFn: () => projectsApi.getConfig(projectId).then((r) => r.data as Record<string, unknown>),
    enabled: !!projectId,
  });

  const mutation = useMutation({
    mutationFn: (updates: Record<string, unknown>) =>
      projectsApi.patchConfig(projectId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-config', projectId] });
      // Also invalidate overview since it reads from config
      queryClient.invalidateQueries({ queryKey: ['overview', projectId] });
    },
  });

  const handleSave = useCallback(
    async (key: string, value: unknown) => {
      await mutation.mutateAsync({ [key]: value });
    },
    [mutation],
  );

  const gateChecks = useMemo(() => {
    if (!config) return [];
    const gc = config.gate_checks as Record<string, unknown> | undefined;
    return (gc?.checks as GateCheck[]) ?? [];
  }, [config]);

  const gateMaxFix = useMemo(() => {
    if (!config) return 3;
    const gc = config.gate_checks as Record<string, unknown> | undefined;
    return (gc?.max_fix_cycles as number) ?? 3;
  }, [config]);

  // All sections: parameter groups + gate checks as a virtual tab
  // (must be above early return to satisfy rules of hooks)
  const allSections = useMemo(() => [
    ...PARAMETER_GROUPS.map((g) => ({ id: g.id, title: g.title, icon: g.icon })),
    { id: 'gate_checks', title: 'Gate Checks', icon: <SettingsIcon className="w-4 h-4" /> },
  ], []);

  const [activeSection, setActiveSection] = useState(allSections[0].id);

  if (isLoading || !config) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-text-muted">
          <div className="w-5 h-5 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
          Loading configuration...
        </div>
      </div>
    );
  }

  const activeGroup = PARAMETER_GROUPS.find((g) => g.id === activeSection);

  return (
    <div className="flex gap-0 rounded-xl border border-border-subtle overflow-hidden min-h-[480px]">
      {/* Vertical sub-tab sidebar */}
      <div className="w-52 shrink-0 bg-bg-secondary/70 border-r border-border-subtle">
        <div className="p-3 border-b border-border-subtle">
          <p className="text-[10px] text-text-muted">
            Auto-saved on blur
          </p>
        </div>
        <nav className="py-1">
          {allSections.map((section) => (
            <button
              key={section.id}
              onClick={() => setActiveSection(section.id)}
              className={clsx(
                'w-full flex items-center gap-2.5 px-4 py-2.5 text-sm transition-colors',
                activeSection === section.id
                  ? 'bg-bg-tertiary text-accent-cyan border-l-2 border-accent-cyan'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover border-l-2 border-transparent',
              )}
            >
              <div className={clsx(
                'shrink-0',
                activeSection === section.id ? 'text-accent-cyan' : 'text-text-muted',
              )}>
                {section.icon}
              </div>
              <span className="truncate">{section.title}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Content area — full remaining width */}
      <div className="flex-1 p-5 overflow-y-auto">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeSection}
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.12 }}
          >
            {activeGroup ? (
              <GroupContent
                group={activeGroup}
                config={config}
                onSave={handleSave}
              />
            ) : activeSection === 'gate_checks' ? (
              <GateChecksEditor
                checks={gateChecks}
                maxFixCycles={gateMaxFix}
                onSave={handleSave}
              />
            ) : null}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
