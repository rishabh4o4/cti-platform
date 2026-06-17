/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { useAlertWebSocket } from '@/hooks/useAlertWebSocket';
import { RiskBadge } from '@/components/shared/RiskBadge';
import { CheckCircle, AlertTriangle, X, Filter, UserPlus, ArrowUpRight, Clock, FileText, CheckCheck } from 'lucide-react';
import { ErrorState } from '@/components/shared/ErrorState';
import { TableSkeleton } from '@/components/shared/Skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import toast from 'react-hot-toast';
import { usePermission } from '@/lib/rbac';
import { Permission } from '@/types';
import { useAuthStore } from '@/store/useAuthStore';
import { Settings } from 'lucide-react';

const fetchAlerts = async () => (await api.get('/alerts')).data;

const resolveAlert = async (id: string) => {
  return (await api.patch(`/alerts/${id}/resolve`, { analyst_note: null, suppress_minutes: 0 })).data;
};

const AlertRow = React.memo(({ alert, resolveMutation, canExportPdf, canAcknowledge }: any) => {
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerateReport = async () => {
    try {
      setIsGenerating(true);
      const res = await api.post(`/export/${alert.content_id}/pdf`, null, {
        responseType: 'blob',
        params: { source_reliability_rating: 'C / 2' }
      });
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `evidence_report_CASE-${alert.content_id.slice(0, 8).toUpperCase()}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('Report downloaded');
    } catch {
      toast.error('Failed to generate PDF report');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <tr className="hover:bg-background/50 transition-colors">
      <td className="px-6 py-4 whitespace-nowrap"><RiskBadge level={alert.severity} /></td>
      <td className="px-6 py-4 text-text-primary font-medium">{alert.title}</td>
      <td className="px-6 py-4 text-text-secondary">{alert.source}</td>
      <td className="px-6 py-4 text-text-secondary">{new Date(alert.timestamp).toLocaleString()}</td>
      <td className="px-6 py-4 text-right">
        <div className="flex justify-end gap-1">
          <button 
            disabled
            aria-label="Assign alert to analyst — Coming soon"
            className="inline-flex items-center justify-center p-2 rounded-md text-text-secondary/50 cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
            title="Coming soon — Phase 2"
          >
            <UserPlus className="h-4 w-4" />
          </button>
          <button 
            disabled
            aria-label="Escalate alert — Coming soon"
            className="inline-flex items-center justify-center p-2 rounded-md text-text-secondary/50 cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-critical"
            title="Coming soon — Phase 2"
          >
            <ArrowUpRight className="h-4 w-4" />
          </button>
          <button 
            disabled
            aria-label="Snooze alert — Coming soon"
            className="inline-flex items-center justify-center p-2 rounded-md text-text-secondary/50 cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-medium"
            title="Coming soon — Phase 2"
          >
            <Clock className="h-4 w-4" />
          </button>
          <button 
            onClick={handleGenerateReport}
            disabled={isGenerating || !canExportPdf}
            aria-label="Generate evidence report"
            className="inline-flex items-center justify-center p-2 rounded-md text-text-secondary hover:bg-primary/10 hover:text-primary transition-colors focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
            title="Generate Evidence Report"
          >
            <FileText className={`h-4 w-4 ${isGenerating ? 'animate-pulse text-primary' : ''}`} />
          </button>
          <div className="w-px h-6 bg-border mx-1 self-center"></div>
          <button 
            onClick={() => resolveMutation.mutate(alert.id)}
            disabled={alert.resolved || resolveMutation.isPending || !canAcknowledge}
            aria-label={alert.resolved ? "Alert resolved" : "Resolve alert"}
            className="inline-flex items-center justify-center p-2 rounded-md text-text-secondary hover:bg-low/10 hover:text-low disabled:opacity-50 disabled:cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-low"
            title={alert.resolved ? "Already resolved" : "Resolve Alert"}
          >
            <CheckCircle className="h-4 w-4" />
          </button>
        </div>
      </td>
    </tr>
  );
});

export default function AlertCenter() {
  const user = useAuthStore((state) => state.user);
  const queryClient = useQueryClient();
  const { alerts: wsAlerts } = useAlertWebSocket();
  const [acknowledgedWsAlerts, setAcknowledgedWsAlerts] = useState<Set<string>>(new Set());

  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [highThreshold, setHighThreshold] = useState('75');
  const [criticalThreshold, setCriticalThreshold] = useState('90');

  const { data: configData } = useQuery({
    queryKey: ['alertConfig'],
    queryFn: async () => (await api.get('/alerts/config')).data,
    enabled: user?.role === 'admin'
  });

  React.useEffect(() => {
    if (configData) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setHighThreshold(configData.high_threshold.toString());
      setCriticalThreshold(configData.critical_threshold.toString());
    }
  }, [configData]);

  const configMutation = useMutation({
    mutationFn: async () => {
      await api.post('/alerts/config', { 
        high_threshold: parseFloat(highThreshold), 
        critical_threshold: parseFloat(criticalThreshold),
        notification_channels: configData?.notification_channels || [] 
      });
    },
    onSuccess: () => {
      toast.success('Alert configuration updated');
      setIsConfigOpen(false);
      queryClient.invalidateQueries({ queryKey: ['alertConfig'] });
    },
    onError: () => toast.error('Failed to update config')
  });

  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [dateFilter, setDateFilter] = useState<string>('all');
  const [customFrom, setCustomFrom] = useState<string>('');
  const [customTo, setCustomTo] = useState<string>('');

  const canExportPdf = usePermission(Permission.EXPORT_PDF);
  const canAcknowledge = usePermission(Permission.ACKNOWLEDGE_ALERTS);

  const { data: dbAlerts, isLoading, isError, refetch } = useQuery({
    queryKey: ['alerts'],
    queryFn: fetchAlerts,
  });

  const resolveMutation = useMutation({
    mutationFn: resolveAlert,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      toast.success('Alert resolved');
    },
    onError: () => toast.error('Failed to resolve alert'),
  });

  const burstAlerts = wsAlerts.filter(a => a.isBurst && !acknowledgedWsAlerts.has(a.id));
  const individualWsAlerts = wsAlerts.filter(a => !a.isBurst && !acknowledgedWsAlerts.has(a.id));

  let allDisplayAlerts = [...(dbAlerts || []), ...individualWsAlerts].filter((v, i, a) => a.findIndex(t => t.id === v.id) === i);

  if (severityFilter !== 'all') {
    allDisplayAlerts = allDisplayAlerts.filter(a => a.severity === severityFilter);
  }
  if (sourceFilter !== 'all') {
    allDisplayAlerts = allDisplayAlerts.filter(a => (a.source || 'unknown').toLowerCase() === sourceFilter.toLowerCase());
  }
  if (dateFilter === 'custom') {
    if (customFrom) {
      const from = new Date(customFrom);
      allDisplayAlerts = allDisplayAlerts.filter(a => new Date(a.timestamp || a.created_at) >= from);
    }
    if (customTo) {
      const to = new Date(customTo);
      to.setHours(23, 59, 59, 999);
      allDisplayAlerts = allDisplayAlerts.filter(a => new Date(a.timestamp || a.created_at) <= to);
    }
  } else if (dateFilter !== 'all') {
    const now = new Date();
    const cutoff = new Date();
    if (dateFilter === '24h') cutoff.setHours(now.getHours() - 24);
    if (dateFilter === '7d') cutoff.setDate(now.getDate() - 7);
    if (dateFilter === '30d') cutoff.setDate(now.getDate() - 30);
    allDisplayAlerts = allDisplayAlerts.filter(a => new Date(a.timestamp || a.created_at) >= cutoff);
  }

  const handleAcknowledgeBurst = (id: string) => {
    setAcknowledgedWsAlerts(prev => new Set(prev).add(id));
  };

  const handleAcknowledgeAll = () => {
    setAcknowledgedWsAlerts(prev => {
      const next = new Set(prev);
      burstAlerts.forEach(a => next.add(a.id));
      return next;
    });
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {burstAlerts.length > 0 && (
        <div className="bg-critical/10 border border-critical rounded-lg p-4 mb-6 shadow-sm" role="status" aria-live="polite">
          <div className="flex items-start">
            <AlertTriangle className="h-5 w-5 text-critical mr-3 mt-0.5 shrink-0" />
            <div className="flex-1">
              <h3 className="text-critical font-semibold mb-1">Alert Burst Detected</h3>
              <p className="text-sm text-text-secondary">We detected a sudden surge of {burstAlerts.length} correlated alerts. This may indicate an ongoing coordinated campaign.</p>
              <div className="mt-3 flex gap-2 overflow-x-auto pb-2">
                {burstAlerts.slice(0, 5).map(alert => (
                  <div key={alert.id} className="bg-surface border border-border rounded px-3 py-1.5 text-xs whitespace-nowrap flex items-center gap-2">
                    <RiskBadge level={alert.severity} className="px-1.5 py-0.5 text-[10px]" />
                    <span className="text-text-primary font-medium">{alert.title || alert.raw_text || 'Threat Detected'}</span>
                    <button onClick={() => handleAcknowledgeBurst(alert.id)} className="ml-2 text-text-secondary hover:text-text-primary" aria-label={`Dismiss ${alert.title}`}>
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
                {burstAlerts.length > 5 && (
                  <div className="bg-surface border border-border rounded px-3 py-1.5 text-xs flex items-center text-text-secondary font-medium">
                    +{burstAlerts.length - 5} more
                  </div>
                )}
              </div>
            </div>
            <div className="mt-3 flex items-center justify-end">
              <button
                onClick={handleAcknowledgeAll}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-surface border border-border text-text-secondary hover:bg-background hover:text-text-primary transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
                aria-label="Acknowledge all burst alerts"
              >
                <CheckCheck className="h-3.5 w-3.5" />
                Acknowledge All
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-surface border border-border rounded-xl shadow-sm overflow-hidden flex flex-col">
        <div className="p-4 border-b border-border flex flex-col sm:flex-row sm:items-center gap-4 bg-surface">
          <div className="flex items-center text-sm font-medium text-text-primary">
            <Filter className="h-4 w-4 mr-2 text-text-secondary" />
            Filters
          </div>
          <div className="flex flex-wrap gap-3 flex-1">
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="bg-background border border-border rounded-md text-sm px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-surface text-text-primary"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="bg-background border border-border rounded-md text-sm px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-surface text-text-primary"
            >
              <option value="all">All Sources</option>
              <option value="telegram">Telegram</option>
              <option value="reddit">Reddit</option>
              <option value="x">X</option>
            </select>
            <select
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
              className="bg-background border border-border rounded-md text-sm px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-surface text-text-primary"
            >
              <option value="all">All Time</option>
              <option value="24h">Last 24 Hours</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
              <option value="custom">Custom Range</option>
            </select>
            {dateFilter === 'custom' && (
              <>
                <label className="flex items-center gap-2 text-sm text-text-primary">
                  <span className="sr-only">From Date</span>
                  <input
                    type="date"
                    value={customFrom}
                    onChange={(e) => setCustomFrom(e.target.value)}
                    className="bg-background border border-border rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-surface"
                  />
                </label>
                <span className="text-text-secondary text-sm">to</span>
                <label className="flex items-center gap-2 text-sm text-text-primary">
                  <span className="sr-only">To Date</span>
                  <input
                    type="date"
                    value={customTo}
                    onChange={(e) => setCustomTo(e.target.value)}
                    className="bg-background border border-border rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-surface"
                  />
                </label>
              </>
            )}
          </div>
          {user?.role === 'admin' && (
            <button
              onClick={() => setIsConfigOpen(true)}
              className="flex items-center gap-2 px-3 py-1.5 bg-surface border border-border text-text-secondary rounded-md hover:bg-background hover:text-text-primary transition-colors focus:outline-none focus:ring-2 focus:ring-primary font-medium text-sm ml-auto"
            >
              <Settings className="h-4 w-4" />
              Configure Alerts
            </button>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-background border-b border-border">
              <tr>
                <th className="px-6 py-4 font-medium text-text-secondary">Severity</th>
                <th className="px-6 py-4 font-medium text-text-secondary">Title</th>
                <th className="px-6 py-4 font-medium text-text-secondary">Source</th>
                <th className="px-6 py-4 font-medium text-text-secondary">Time</th>
                <th className="px-6 py-4 font-medium text-right text-text-secondary">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                <tr><td colSpan={5} className="p-6"><TableSkeleton cols={5} rows={5} /></td></tr>
              ) : isError ? (
                <tr><td colSpan={5} className="p-0"><ErrorState onRetry={refetch} className="rounded-none border-x-0 border-b-0" /></td></tr>
              ) : allDisplayAlerts.length === 0 ? (
                <tr><td colSpan={5} className="p-0"><EmptyState title="No alerts found" message="There are no alerts matching your current filters." className="rounded-none border-x-0 border-b-0" /></td></tr>
              ) : allDisplayAlerts.map((alert: any) => (
                <AlertRow key={alert.id} alert={alert} resolveMutation={resolveMutation} canExportPdf={canExportPdf} canAcknowledge={canAcknowledge} />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {isConfigOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface border border-border rounded-xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="flex justify-between items-center p-6 border-b border-border">
              <h2 className="text-xl font-bold text-text-primary">Alert Configuration</h2>
              <button onClick={() => setIsConfigOpen(false)} className="text-text-secondary hover:text-text-primary">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">High Severity Threshold Score</label>
                <input 
                  type="number"
                  value={highThreshold}
                  onChange={(e) => setHighThreshold(e.target.value)}
                  className="w-full bg-background border border-border focus:ring-primary rounded-md px-3 py-2 text-text-primary focus:outline-none focus:ring-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Critical Severity Threshold Score</label>
                <input 
                  type="number"
                  value={criticalThreshold}
                  onChange={(e) => setCriticalThreshold(e.target.value)}
                  className="w-full bg-background border border-border focus:ring-primary rounded-md px-3 py-2 text-text-primary focus:outline-none focus:ring-2"
                />
              </div>
              <div className="pt-4 flex justify-end gap-3">
                <button 
                  type="button"
                  onClick={() => setIsConfigOpen(false)}
                  className="px-4 py-2 border border-border text-text-primary rounded-md hover:bg-background transition-colors"
                >
                  Cancel
                </button>
                <button 
                  type="button"
                  onClick={() => configMutation.mutate()}
                  disabled={configMutation.isPending}
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {configMutation.isPending ? 'Saving...' : 'Save Settings'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
