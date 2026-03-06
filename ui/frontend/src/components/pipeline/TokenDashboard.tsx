import { pipelineApi } from '@/api/client';
import { useQuery } from '@tanstack/react-query';
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

interface TokenDashboardProps {
  projectId?: number;
}

const COLORS = ['#06b6d4', '#a855f7', '#3b82f6', '#10b981', '#f59e0b', '#ef4444'];

export function TokenDashboard({ projectId }: TokenDashboardProps) {
  const { data: tokenData, isLoading } = useQuery({
    queryKey: ['tokens', projectId],
    queryFn: () => pipelineApi.getTokens(projectId!).then((res) => res.data),
    enabled: !!projectId,
  });

  if (isLoading) {
    return (
      <div className="bg-bg-secondary rounded-lg p-6">
        <p className="text-text-muted">Loading token data...</p>
      </div>
    );
  }

  if (!tokenData) {
    return (
      <div className="bg-bg-secondary rounded-lg p-6">
        <p className="text-text-muted">No token usage data available</p>
      </div>
    );
  }

  // Prepare bar chart data from by_milestone
  const barData = Object.entries(tokenData.by_milestone).map(([id, data]) => ({
    name: `M${id}`,
    input: data.input_tokens,
    output: data.output_tokens,
    cost: data.cost_usd,
  }));

  // Prepare pie chart data
  const pieData = Object.entries(tokenData.by_milestone).map(([id, data]) => ({
    name: `Milestone ${id}`,
    value: data.cost_usd,
  }));

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-bg-secondary rounded-lg p-4">
          <p className="text-text-muted text-sm">Total Input Tokens</p>
          <p className="text-2xl font-bold text-accent-cyan">
            {tokenData.total.input_tokens.toLocaleString()}
          </p>
        </div>
        <div className="bg-bg-secondary rounded-lg p-4">
          <p className="text-text-muted text-sm">Total Output Tokens</p>
          <p className="text-2xl font-bold text-accent-purple">
            {tokenData.total.output_tokens.toLocaleString()}
          </p>
        </div>
        <div className="bg-bg-secondary rounded-lg p-4">
          <p className="text-text-muted text-sm">Total Cost</p>
          <p className="text-2xl font-bold text-status-success">
            ${tokenData.total.cost_usd.toFixed(4)}
          </p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-6">
        {/* Bar Chart - Token Usage by Milestone */}
        <div className="bg-bg-secondary rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Tokens by Milestone</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="name" stroke="#6b7280" />
              <YAxis stroke="#6b7280" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#111827',
                  border: '1px solid #1f2937',
                  borderRadius: '8px',
                }}
              />
              <Bar dataKey="input" fill="#06b6d4" name="Input" />
              <Bar dataKey="output" fill="#a855f7" name="Output" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Pie Chart - Cost Distribution */}
        <div className="bg-bg-secondary rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Cost Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={5}
                dataKey="value"
              >
                {pieData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: '#111827',
                  border: '1px solid #1f2937',
                  borderRadius: '8px',
                }}
                formatter={(value: number) => [`$${value.toFixed(4)}`, 'Cost']}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
