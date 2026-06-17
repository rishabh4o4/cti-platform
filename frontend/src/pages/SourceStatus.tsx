/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '@/lib/api';
import { Activity, Database, RefreshCw, Play } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuthStore } from '@/store/useAuthStore';
import { ErrorState } from '@/components/shared/ErrorState';
import { Skeleton } from '@/components/shared/Skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { DEFAULT_SOURCE_MOCK_STATUS } from '@/config/sources';

const fetchSources = async () => (await api.get('/collectors/status')).data.runs;

function getRelativeTime(dateString: string) {
  const diff = Date.now() - new Date(dateString).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes} min${minutes > 1 ? 's' : ''} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr${hours > 1 ? 's' : ''} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days > 1 ? 's' : ''} ago`;
}

function isSourceMock(source: any) {
  if (source.metadata?.is_mock !== undefined) {
    return source.metadata.is_mock;
  }
  console.debug(`[SourceStatus] is_mock missing in metadata for source ${source.source}. Falling back to DEFAULT_SOURCE_MOCK_STATUS.`);
  return DEFAULT_SOURCE_MOCK_STATUS[source.source] ?? false;
}

export default function SourceStatus() {
  const user = useAuthStore((state) => state.user);

  const { data: sources, isLoading, isError, refetch } = useQuery({
    queryKey: ['sourceStatus'],
    queryFn: fetchSources,
  });

  const triggerMutation = useMutation({
    mutationFn: async (sourceId: string) => {
      await api.post('/collectors/run', { source_id: sourceId });
    },
    onSuccess: () => {
      toast.success('Collection triggered successfully');
      refetch();
    },
    onError: () => {
      toast.error('Failed to trigger collection');
    }
  });

  return (
    <div className="max-w-6xl mx-auto space-y-6">      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {isLoading ? (
          Array.from({length: 3}).map((_, i) => (
            <div key={i} className="bg-surface border border-border rounded-xl p-6 shadow-sm flex flex-col">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center">
                  <Skeleton className="h-12 w-12 rounded-lg mr-3" />
                  <div>
                    <Skeleton className="h-5 w-24 mb-1" />
                    <Skeleton className="h-3 w-16" />
                  </div>
                </div>
                <Skeleton className="h-6 w-16 rounded-full" />
              </div>
              <div className="mt-auto space-y-3 border-t border-border pt-4">
                <div className="flex justify-between items-center"><Skeleton className="h-4 w-20" /><Skeleton className="h-4 w-16" /></div>
                <div className="flex justify-between items-center"><Skeleton className="h-4 w-20" /><Skeleton className="h-4 w-16" /></div>
              </div>
            </div>
          ))
        ) : isError ? (
          <div className="col-span-1 lg:col-span-3">
            <ErrorState title="Failed to load sources" message="An error occurred while fetching source status data." onRetry={refetch} />
          </div>
        ) : sources && sources.length === 0 ? (
          <div className="col-span-1 lg:col-span-3">
            <EmptyState title="No sources configured" message="There are no active intelligence sources." />
          </div>
        ) : sources?.map((source: any) => (
          <div key={source.id} className="bg-surface border border-border rounded-xl p-6 shadow-sm flex flex-col">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center">
                <div className={`p-3 rounded-lg mr-3 ${source.status === 'running' ? 'bg-primary/10 text-primary' : 'bg-surface border border-border text-text-secondary'}`}>
                  {source.status === 'running' ? <Activity className="h-6 w-6" /> : <Database className="h-6 w-6" />}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold text-text-primary capitalize">{source.source}</h3>
                    {isSourceMock(source) ? (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-surface border border-border text-text-secondary">Mock</span>
                    ) : (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-primary/10 border border-primary/20 text-primary flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>Live</span>
                    )}
                  </div>
                  <span className="text-xs text-text-secondary capitalize">{source.trigger_type}</span>
                </div>
              </div>
              <div className="flex flex-col items-end gap-2">
                <span className={`px-2.5 py-1 rounded-full text-xs font-medium uppercase tracking-wide border ${
                  source.status === 'running' ? 'bg-primary/10 text-primary border-primary/20' : source.status === 'failed' ? 'bg-critical/10 text-critical border-critical/20' : 'bg-background text-text-secondary border-border'
                }`}>
                  {source.status}
                </span>
                {user?.role === 'admin' && (
                  <button
                    onClick={() => triggerMutation.mutate(source.source)}
                    disabled={source.status === 'running' || triggerMutation.isPending}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-surface border border-border text-text-secondary hover:bg-background hover:text-text-primary disabled:opacity-50 transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
                    title="Trigger Collector"
                  >
                    <Play className="h-3 w-3" />
                    Trigger
                  </button>
                )}
              </div>
            </div>
            
            <div className="mt-auto space-y-3 border-t border-border pt-4">
              <div className="flex justify-between items-center text-sm">
                <span className="text-text-secondary flex items-center">
                  <RefreshCw className="h-4 w-4 mr-1.5" /> Last Run
                </span>
                <span className="text-text-primary cursor-help" title={new Date(source.started_at).toLocaleString()}>
                  {getRelativeTime(source.started_at)}
                </span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-text-secondary flex items-center">
                  <Activity className="h-4 w-4 mr-1.5" /> Health
                </span>
                <span className={`font-medium capitalize ${
                  source.status === 'failed' ? 'text-critical' : 'text-low'
                }`}>
                  {source.status === 'failed' ? 'error' : 'healthy'}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
