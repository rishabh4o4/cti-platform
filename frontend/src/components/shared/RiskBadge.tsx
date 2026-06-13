import { type RiskLabel } from '@/types';
import { cn } from '@/lib/utils';

interface RiskBadgeProps {
  level: RiskLabel;
  className?: string;
}

const severityConfig: Record<RiskLabel, { className: string; label: string; shape: string }> = {
  low: { className: 'text-low border border-low bg-surface', label: 'Low Risk', shape: '▪' },
  medium: { className: 'text-medium border border-medium bg-surface', label: 'Medium Risk', shape: '▲' },
  high: { className: 'text-high border border-high bg-surface', label: 'High Risk', shape: '●' },
  critical: { className: 'text-critical border border-critical bg-surface', label: 'Critical Risk', shape: '◆' },
};

export function RiskBadge({ level, className }: RiskBadgeProps) {
  const config = severityConfig[level] || severityConfig.low;
  
  return (
    <span
      className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider', config.className, className)}
      role="status"
      aria-label={`Risk level: ${config.label}`}
    >
      <span aria-hidden="true">{config.shape}</span>
      {level}
    </span>
  );
}
