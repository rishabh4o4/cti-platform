import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { Activity, ServerCrash, CheckCircle2, AlertTriangle, HelpCircle } from 'lucide-react';
import { ErrorState } from '@/components/shared/ErrorState';
import { Skeleton } from '@/components/shared/Skeleton';

interface HealthComponent {
  name: string;
  status: 'LIVE' | 'MOCK' | 'OFFLINE' | 'ERROR';
  latency_ms: number;
  detail: string;
}

interface SystemHealthResponse {
  checked_at: string;
  overall: 'HEALTHY' | 'DEGRADED' | 'CRITICAL';
  components: HealthComponent[];
}

const fetchSystemHealth = async (): Promise<SystemHealthResponse> => {
  const response = await api.get('/health/system');
  return response.data;
};

export function SystemHealth() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['systemHealth'],
    queryFn: fetchSystemHealth,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  if (isError) {
    return (
      <div className="bg-surface border border-border rounded-xl p-4 md:p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-text-primary mb-4 flex items-center gap-2">
          <Activity className="h-5 w-5" />
          System Health
        </h2>
        <div className="h-48 flex items-center justify-center">
           <ErrorState 
             title="Health check unavailable" 
             message="Could not reach the system health endpoint." 
             onRetry={refetch} 
             className="border-none shadow-none" 
           />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface border border-border rounded-xl p-4 md:p-6 shadow-sm flex flex-col h-full">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
          <Activity className="h-5 w-5" />
          System Health
        </h2>
        {isLoading ? (
          <Skeleton className="h-6 w-20 rounded-full" />
        ) : (
          <div className={`px-2.5 py-1 text-xs font-semibold rounded-full border ${
            data?.overall === 'HEALTHY' ? 'bg-low/10 text-low border-low/20' : 
            data?.overall === 'DEGRADED' ? 'bg-medium/10 text-medium border-medium/20' : 
            'bg-critical/10 text-critical border-critical/20'
          }`}>
            {data?.overall || 'UNKNOWN'}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {isLoading ? (
          Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="p-3 rounded-lg border border-border flex items-center justify-between">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-12" />
            </div>
          ))
        ) : (
          data?.components?.map((comp, idx) => {
            let statusColor = 'text-text-secondary';
            let StatusIcon = HelpCircle;

            if (comp.status === 'LIVE') {
              statusColor = 'text-low';
              StatusIcon = CheckCircle2;
            } else if (comp.status === 'MOCK') {
              statusColor = 'text-medium';
              StatusIcon = AlertTriangle;
            } else if (comp.status === 'OFFLINE') {
              statusColor = 'text-text-secondary';
              StatusIcon = ServerCrash;
            } else if (comp.status === 'ERROR') {
              statusColor = 'text-critical';
              StatusIcon = ServerCrash;
            }

            return (
              <div 
                key={idx} 
                className="p-3 rounded-lg border border-border flex items-center justify-between bg-surface-hover/30"
                title={comp.detail}
              >
                <span className="text-sm font-medium text-text-primary">{comp.name}</span>
                <div className={`flex items-center gap-1.5 text-xs font-semibold ${statusColor}`}>
                  {comp.status}
                  <StatusIcon className="h-3.5 w-3.5" />
                </div>
              </div>
            );
          })
        )}
      </div>
      
      {!isLoading && data?.checked_at && (
        <div className="mt-4 text-right text-xs text-text-secondary">
          Last checked: {new Date(data.checked_at).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}
