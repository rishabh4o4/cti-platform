/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQuery } from '@tanstack/react-query';
import { Activity, Bell, Shield, SignalHigh, TrendingUp, TrendingDown } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import api from '@/lib/api';
import { Link } from 'react-router-dom';
import { RiskBadge } from '@/components/shared/RiskBadge';
import { FileText } from 'lucide-react';
import { useState } from 'react';
import toast from 'react-hot-toast';

import { ErrorState } from '@/components/shared/ErrorState';
import { Skeleton } from '@/components/shared/Skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { usePermission } from '@/lib/rbac';
import { Permission } from '@/types';
import { SystemHealth } from '@/components/dashboard/SystemHealth';

const fetchSummary = async () => (await api.get('/dashboard/summary')).data;

const fetchHeatmap = async () => (await api.get('/dashboard/heatmap')).data;

const fetchTopThreats = async () => (await api.get('/dashboard/top-threats')).data;

function ThreatRow({ threat, canExportPdf }: { threat: any, canExportPdf: boolean }) {
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerateReport = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      setIsGenerating(true);
      const res = await api.post(`/export/${threat.content_id}/pdf`, null, {
        responseType: 'blob',
        params: { source_reliability_rating: 'C / 2' }
      });
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `evidence_report_CASE-${threat.content_id.slice(0, 8).toUpperCase()}.pdf`;
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
    <Link to={`/investigation/${threat.content_id}`} className="flex flex-col p-3 rounded-lg border border-border hover:bg-border/50 transition-colors group relative">
      <div className="flex justify-between items-start mb-2">
        <span className="text-sm font-medium text-text-primary line-clamp-1 mr-2">{threat.raw_text_preview || 'No text content available'}</span>
        <RiskBadge level={threat.risk_label} />
      </div>
      <div className="flex justify-between items-center text-xs text-text-secondary mt-1">
        <span>{threat.source}</span>
        <div className="flex items-center gap-3">
          <span>{new Date(threat.analyzed_at).toLocaleString()}</span>
          {canExportPdf && (
            <button 
              onClick={handleGenerateReport}
              disabled={isGenerating}
              aria-label="Generate evidence report"
              className="hidden group-hover:flex items-center justify-center p-1.5 rounded-md text-text-secondary hover:bg-primary/10 hover:text-primary transition-colors focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
              title="Generate Evidence Report"
            >
              <FileText className={`h-3.5 w-3.5 ${isGenerating ? 'animate-pulse text-primary' : ''}`} />
            </button>
          )}
        </div>
      </div>
    </Link>
  );
}

function StatCard({ title, value, icon: Icon, colorClass, trend, trendInverse }: any) {
  const hasTrend = trend !== undefined && trend !== null && isFinite(trend);
  const isNegativeTrend = trendInverse ? trend > 0 : trend < 0;
  const isPositiveTrend = trendInverse ? trend < 0 : trend > 0;

  return (
    <div className="bg-surface border border-border rounded-xl p-6 flex items-center shadow-sm">
      <div className={`p-4 rounded-lg mr-4 ${colorClass}`}>
        <Icon className="h-6 w-6" />
      </div>
      <div>
        <h3 className="text-sm font-medium text-text-secondary">{title}</h3>
        <p className="text-2xl font-bold text-text-primary">{value}</p>
        {hasTrend && (
          <div className={`flex items-center gap-1 mt-1 text-xs font-medium ${
            isNegativeTrend ? 'text-critical' : isPositiveTrend ? 'text-low' : 'text-text-secondary'
          }`}>
            {trend > 0 ? <TrendingUp className="h-3 w-3" /> : trend < 0 ? <TrendingDown className="h-3 w-3" /> : null}
            <span>{trend > 0 ? '+' : ''}{trend.toFixed(0)}% vs yesterday</span>
          </div>
        )}
      </div>
    </div>
  );
}

/** Compute % change between the last two days of the trend data */
function computeTrend(trendData: any[] | undefined): number | undefined {
  if (!trendData || trendData.length < 2) return undefined;
  const today = trendData[trendData.length - 1]?.count ?? 0;
  const yesterday = trendData[trendData.length - 2]?.count ?? 0;
  if (yesterday === 0) return today > 0 ? 100 : 0;
  return ((today - yesterday) / yesterday) * 100;
}

export default function Dashboard() {
  const { data: summary, isLoading: isLoadingSummary, isError: isErrorSummary, refetch: refetchSummary } = useQuery({ queryKey: ['dashboardSummary'], queryFn: fetchSummary });
  const { isLoading: isLoadingHeatmap, isError: isErrorHeatmap, refetch: refetchHeatmap } = useQuery({ queryKey: ['dashboardHeatmap'], queryFn: fetchHeatmap });
  const { data: topThreats, isLoading: isLoadingThreats, isError: isErrorThreats, refetch: refetchThreats } = useQuery({ queryKey: ['dashboardTopThreats'], queryFn: fetchTopThreats });

  const itemsTrend = computeTrend(summary?.seven_day_trend);
  const canExportPdf = usePermission(Permission.EXPORT_PDF);

  return (
    <div className="space-y-6">
      {isErrorSummary ? (
        <ErrorState title="Failed to load summary" message="Could not fetch dashboard summary metrics." onRetry={refetchSummary} />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
          <StatCard title="Total Items (24h)" value={isLoadingSummary ? <Skeleton className="h-8 w-16 mt-1" /> : summary?.total_items_24h} icon={Activity} colorClass="bg-primary/10 text-primary" trend={isLoadingSummary ? undefined : itemsTrend} />
          <StatCard title="Active Alerts" value={isLoadingSummary ? <Skeleton className="h-8 w-16 mt-1" /> : summary?.open_alerts} icon={Bell} colorClass="bg-high/10 text-high" trendInverse />
          <StatCard title="Avg Risk Score" value={isLoadingSummary ? <Skeleton className="h-8 w-16 mt-1" /> : summary?.average_risk_score} icon={Shield} colorClass="bg-critical/10 text-critical" trendInverse />
          <StatCard title="Monitored Sources" value={isLoadingSummary ? <Skeleton className="h-8 w-16 mt-1" /> : Object.keys(summary?.items_by_source || {}).length} icon={SignalHigh} colorClass="bg-low/10 text-low" />
        </div>
      )}

      <SystemHealth />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6">
        <div className="lg:col-span-2 bg-surface border border-border rounded-xl p-4 md:p-6 shadow-sm order-2 lg:order-1">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Discovery Trend</h2>
          {isLoadingHeatmap ? (
            <div className="h-72 w-full flex items-end gap-2 pb-4">
              {Array.from({length: 7}).map((_, i) => <Skeleton key={i} className="w-full flex-1" style={{height: `${(i * 17 % 60) + 20}%`}} />)}
            </div>
          ) : isErrorHeatmap ? (
            <div className="h-72 w-full flex items-center justify-center">
              <ErrorState title="Failed to load chart" message="Could not fetch trend data." onRetry={refetchHeatmap} className="border-none shadow-none" />
            </div>
          ) : summary?.seven_day_trend && summary.seven_day_trend.length === 0 ? (
            <div className="h-72 w-full flex items-center justify-center">
              <EmptyState title="No Trend Data" message="There is no discovery trend data to display." className="border-none shadow-none" />
            </div>
          ) : (
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={summary?.seven_day_trend || []}>
                  <defs>
                    <linearGradient id="colorRisk" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="var(--primary)" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="day" stroke="var(--text-secondary)" tick={{fill: 'var(--text-secondary)'}} />
                  <YAxis stroke="var(--text-secondary)" tick={{fill: 'var(--text-secondary)'}} />
                  <Tooltip contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
                  <Area type="monotone" dataKey="count" stroke="var(--primary)" fillOpacity={1} fill="url(#colorRisk)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="bg-surface border border-border rounded-xl p-4 md:p-6 shadow-sm flex flex-col h-full order-1 lg:order-2">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Recent Top Threats</h2>
          <div className="space-y-4 flex-1">
            {isLoadingThreats ? (
              Array.from({length: 4}).map((_, i) => (
                <div key={i} className="p-3 rounded-lg border border-border">
                  <div className="flex justify-between items-start mb-2">
                    <Skeleton className="h-4 w-2/3" />
                    <Skeleton className="h-4 w-16" />
                  </div>
                  <div className="flex justify-between items-center mt-2">
                    <Skeleton className="h-3 w-16" />
                    <Skeleton className="h-3 w-16" />
                  </div>
                </div>
              ))
            ) : isErrorThreats ? (
              <ErrorState title="Failed to load" message="Could not fetch recent threats." onRetry={refetchThreats} className="border-none shadow-none p-4" />
            ) : topThreats && topThreats.length === 0 ? (
              <EmptyState title="No Active Threats" message="There are currently no top threats to display." className="border-none shadow-none p-4" />
            ) : (
              topThreats?.map((threat: any) => (
                <ThreatRow key={threat.content_id} threat={threat} canExportPdf={canExportPdf} />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
