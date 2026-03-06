import { pipelineApi } from '@/api/client';
import { Badge } from '@/components/shared/Badge';
import { useQuery } from '@tanstack/react-query';

interface MilestoneListProps {
  projectId?: number;
}

export function MilestoneList({ projectId }: MilestoneListProps) {
  const { data: milestones, isLoading } = useQuery({
    queryKey: ['milestones', projectId],
    queryFn: () => pipelineApi.getMilestones(projectId!).then((res) => res.data),
    enabled: !!projectId,
    refetchInterval: 5000,
  });

  if (isLoading) {
    return <div className="text-text-muted">Loading milestones...</div>;
  }

  if (!milestones || milestones.length === 0) {
    return <div className="text-text-muted">No milestone data available</div>;
  }

  return (
    <div className="bg-bg-secondary rounded-lg p-6">
      <h3 className="text-lg font-semibold mb-4">Milestones</h3>
      <div className="space-y-3">
        {milestones.map((milestone: any) => (
          <div
            key={milestone.id}
            className="flex items-center justify-between p-3 bg-bg-tertiary rounded-lg"
          >
            <div className="flex items-center space-x-3">
              <span className="font-medium">Milestone {milestone.id}</span>
              <Badge
                variant={
                  milestone.completed_at
                    ? 'success'
                    : milestone.started_at
                    ? 'info'
                    : 'default'
                }
              >
                {milestone.completed_at
                  ? 'Complete'
                  : milestone.started_at
                  ? milestone.phase
                  : 'Pending'}
              </Badge>
            </div>
            <div className="text-sm text-text-muted">
              {milestone.bugfix_cycle > 0 && (
                <span className="mr-2">Bugfix: {milestone.bugfix_cycle}</span>
              )}
              {milestone.test_fix_cycle > 0 && (
                <span>Test Fix: {milestone.test_fix_cycle}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
