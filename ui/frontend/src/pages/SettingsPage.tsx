import { healthApi } from '@/api/client';
import { Badge } from '@/components/shared/Badge';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  RefreshCwIcon,
  SettingsIcon,
  XCircleIcon,
} from 'lucide-react';
import { useEffect } from 'react';

export function SettingsPage() {
  const queryClient = useQueryClient();

  const { data: requirements, isLoading } = useQuery({
    queryKey: ['requirements'],
    queryFn: () => healthApi.getRequirementsStatus().then((res) => res.data),
  });

  const checkMutation = useMutation({
    mutationFn: () => healthApi.checkRequirements(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requirements'] });
    },
  });

  // Auto-invoke checks if no results exist yet
  useEffect(() => {
    if (!isLoading && (!requirements || requirements.length === 0)) {
      checkMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, requirements]);

  const statusIcons: Record<string, React.ReactNode> = {
    passed: <CheckCircleIcon className="w-5 h-5 text-status-success" />,
    failed: <XCircleIcon className="w-5 h-5 text-status-error" />,
    skipped: <AlertTriangleIcon className="w-5 h-5 text-status-warning" />,
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <SettingsIcon className="w-6 h-6 text-text-muted" />
          <h1 className="text-2xl font-bold">Settings</h1>
        </div>
      </div>

      {/* System Requirements */}
      <div className="bg-bg-secondary rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">System Requirements</h3>
          <button
            onClick={() => checkMutation.mutate()}
            disabled={checkMutation.isPending}
            className="flex items-center space-x-2 px-3 py-1.5 bg-bg-tertiary hover:bg-bg-hover rounded transition-colors text-sm"
          >
            <RefreshCwIcon
              className={`w-4 h-4 ${checkMutation.isPending ? 'animate-spin' : ''}`}
            />
            <span>Re-check</span>
          </button>
        </div>

        {isLoading || checkMutation.isPending ? (
          <p className="text-text-muted">Checking requirements...</p>
        ) : requirements && requirements.length > 0 ? (
          <div className="space-y-3">
            {requirements.map((req: any, idx: number) => (
              <div
                key={idx}
                className="flex items-center justify-between p-3 bg-bg-tertiary rounded-lg"
              >
                <div className="flex items-center space-x-3">
                  {statusIcons[req.status] || statusIcons.failed}
                  <span className="font-medium capitalize">
                    {req.requirement_name}
                  </span>
                </div>
                <div className="flex items-center space-x-3">
                  <span className="text-sm text-text-muted">{req.details}</span>
                  <Badge
                    variant={
                      req.status === 'passed'
                        ? 'success'
                        : req.status === 'failed'
                        ? 'error'
                        : 'warning'
                    }
                  >
                    {req.status}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-text-muted">
            No requirement checks found. Checking now...
          </p>
        )}
      </div>

      {/* Manual Fix UI */}
      <div className="bg-bg-secondary rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Manual Intervention</h3>
        <p className="text-text-muted text-sm">
          If automated setup fails after 3 attempts, manual fixes can be applied here.
          This section activates when a project setup enters the "intervention" state.
        </p>
      </div>
    </div>
  );
}
