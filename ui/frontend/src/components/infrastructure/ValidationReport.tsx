import { Badge } from '@/components/shared/Badge';
import type { ValidationReport as ValidationReportType } from '@/types';

interface ValidationReportProps {
  report: ValidationReportType | null;
}

export function ValidationReport({ report }: ValidationReportProps) {
  if (!report) {
    return (
      <div className="bg-bg-secondary rounded-lg p-6">
        <p className="text-text-muted">No validation report available</p>
      </div>
    );
  }

  return (
    <div className="bg-bg-secondary rounded-lg p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Validation Report</h3>
        <Badge variant={report.status === 'passed' ? 'success' : 'error'}>
          {report.status}
        </Badge>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-bg-tertiary rounded p-3 text-center">
          <p className="text-2xl font-bold">{report.summary.total}</p>
          <p className="text-xs text-text-muted">Total</p>
        </div>
        <div className="bg-bg-tertiary rounded p-3 text-center">
          <p className="text-2xl font-bold text-status-success">{report.summary.passed}</p>
          <p className="text-xs text-text-muted">Passed</p>
        </div>
        <div className="bg-bg-tertiary rounded p-3 text-center">
          <p className="text-2xl font-bold text-status-error">{report.summary.failed}</p>
          <p className="text-xs text-text-muted">Failed</p>
        </div>
        <div className="bg-bg-tertiary rounded p-3 text-center">
          <p className="text-2xl font-bold text-status-warning">{report.summary.warnings}</p>
          <p className="text-xs text-text-muted">Warnings</p>
        </div>
      </div>

      {/* Steps */}
      <div className="space-y-2">
        {report.steps.map((step, idx) => (
          <div key={idx} className="p-3 bg-bg-tertiary rounded-lg">
            <div className="flex items-center justify-between">
              <span className="font-medium">{step.name}</span>
              <Badge
                variant={
                  step.status === 'passed'
                    ? 'success'
                    : step.status === 'warning'
                    ? 'warning'
                    : 'error'
                }
              >
                {step.status}
              </Badge>
            </div>
            {step.error && (
              <p className="text-sm text-status-error mt-1">{step.error}</p>
            )}
            {step.fix_suggestion && (
              <p className="text-sm text-accent-cyan mt-1">Fix: {step.fix_suggestion}</p>
            )}
          </div>
        ))}
      </div>

      <p className="text-xs text-text-muted">
        Duration: {report.duration_seconds.toFixed(2)}s
      </p>
    </div>
  );
}
