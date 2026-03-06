import { healthApi } from '@/api/client';
import { Badge } from '@/components/shared/Badge';
import { Card } from '@/components/shared/Card';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
    CheckCircleIcon,
    RefreshCwIcon,
    TerminalIcon,
    XCircleIcon,
} from 'lucide-react';

export function RequirementsPage() {
  const queryClient = useQueryClient();

  const { data: requirements, isLoading, refetch } = useQuery({
    queryKey: ['requirements'],
    queryFn: () => healthApi.checkRequirements().then((res) => res.data),
  });

  const allMet = requirements?.every((r: any) => r.met) ?? false;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">System Requirements</h1>
          <p className="text-text-secondary text-sm mt-1">
            Check that all required tools and dependencies are available
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="btn-secondary flex items-center space-x-2"
        >
          <RefreshCwIcon className="w-4 h-4" />
          <span>Re-check</span>
        </button>
      </div>

      <Card>
        <div className="flex items-center space-x-3 mb-6">
          <div
            className={`w-3 h-3 rounded-full ${
              allMet ? 'bg-status-success' : 'bg-status-warning'
            }`}
          />
          <span className="font-medium">
            {allMet
              ? 'All requirements met'
              : 'Some requirements need attention'}
          </span>
        </div>

        {isLoading ? (
          <p className="text-text-muted text-center py-8">
            Checking requirements...
          </p>
        ) : (
          <div className="space-y-3">
            {requirements?.map((req: any, i: number) => (
              <div
                key={i}
                className="flex items-center justify-between p-4 bg-bg-tertiary rounded-lg"
              >
                <div className="flex items-center space-x-3">
                  {req.met ? (
                    <CheckCircleIcon className="w-5 h-5 text-status-success" />
                  ) : (
                    <XCircleIcon className="w-5 h-5 text-status-error" />
                  )}
                  <div>
                    <p className="font-medium">{req.name}</p>
                    <p className="text-xs text-text-muted">
                      {req.description || req.check}
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  {req.version && (
                    <span className="text-sm text-text-secondary font-mono">
                      v{req.version}
                    </span>
                  )}
                  <Badge variant={req.met ? 'success' : 'error'}>
                    {req.met ? 'Available' : 'Missing'}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {!allMet && (
        <Card title="Installation Help">
          <div className="space-y-4">
            {requirements
              ?.filter((r: any) => !r.met)
              .map((req: any, i: number) => (
                <div key={i} className="p-4 bg-bg-tertiary rounded-lg">
                  <div className="flex items-center space-x-2 mb-2">
                    <TerminalIcon className="w-4 h-4 text-accent-cyan" />
                    <span className="font-medium">{req.name}</span>
                  </div>
                  {req.install_hint && (
                    <pre className="text-sm font-mono bg-bg-primary p-3 rounded mt-2 text-text-secondary">
                      {req.install_hint}
                    </pre>
                  )}
                </div>
              ))}
          </div>
        </Card>
      )}
    </div>
  );
}
