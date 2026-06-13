/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { ErrorState } from '@/components/shared/ErrorState';
import { Skeleton } from '@/components/shared/Skeleton';
import { EmptyState } from '@/components/shared/EmptyState';

const fetchAnalytics = async () => (await api.get('/analysis/stats')).data;

const COLORS = ['var(--primary)', 'var(--critical)', 'var(--high)', 'var(--medium)'];

export default function Analytics() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['analyticsStats'],
    queryFn: fetchAnalytics,
  });

  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-surface border border-border rounded-xl p-6 shadow-sm">
            <Skeleton className="h-6 w-48 mb-4" />
            <Skeleton className="h-80 w-full" />
          </div>
          <div className="bg-surface border border-border rounded-xl p-6 shadow-sm">
            <Skeleton className="h-6 w-48 mb-4" />
            <Skeleton className="h-80 w-full rounded-full max-w-[320px] mx-auto" />
          </div>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="max-w-6xl mx-auto space-y-6">
        <ErrorState title="Failed to load analytics" message="Could not fetch analysis statistics." onRetry={refetch} />
      </div>
    );
  }

  if (!data || (data.label_counts?.length === 0 && data.source_breakdown?.length === 0)) {
    return (
      <div className="max-w-6xl mx-auto space-y-6">
        <EmptyState title="No Analytics Data" message="There is no analytics data available for the current timeframe." />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-surface border border-border rounded-xl p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Threat Categories</h2>
          <div className="h-80 w-full" role="img" aria-label="Bar chart showing threat categories distribution">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data?.label_counts} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                <XAxis type="number" stroke="var(--text-secondary)" tick={{fill: 'var(--text-secondary)'}} />
                <YAxis dataKey="label" type="category" stroke="var(--text-secondary)" tick={{fill: 'var(--text-secondary)'}} />
                <Tooltip contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
                <Bar dataKey="count" fill="var(--primary)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <table className="sr-only">
            <caption>Threat Categories Data</caption>
            <thead>
              <tr><th scope="col">Category</th><th scope="col">Count</th></tr>
            </thead>
            <tbody>
              {data?.label_counts?.map((c: any) => (
                <tr key={c.label}><td>{c.label}</td><td>{c.count}</td></tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="bg-surface border border-border rounded-xl p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Source Distribution</h2>
          <div className="h-80 w-full" role="img" aria-label="Pie chart showing source distribution">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data?.source_breakdown}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="count"
                  nameKey="source"
                >
                  {data?.source_breakdown?.map((_: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex justify-center gap-4 mt-4">
            {data?.source_breakdown?.map((entry: any, index: number) => (
              <div key={entry.source} className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: COLORS[index % COLORS.length] }}></div>
                <span className="text-sm text-text-secondary">{entry.source}</span>
              </div>
              ))}
          </div>
          <table className="sr-only">
            <caption>Source Distribution Data</caption>
            <thead>
              <tr><th scope="col">Source</th><th scope="col">Count</th></tr>
            </thead>
            <tbody>
              {data?.source_breakdown?.map((s: any) => (
                <tr key={s.source}><td>{s.source}</td><td>{s.count}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
