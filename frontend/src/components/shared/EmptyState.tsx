import { Inbox } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EmptyStateProps {
  title?: string;
  message?: string;
  icon?: React.ElementType;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ 
  title = 'No Data Found', 
  message = 'There is currently no data to display here.',
  icon: Icon = Inbox,
  action,
  className
}: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center p-8 text-center bg-surface border border-border rounded-xl shadow-sm', className)}>
      <div className="bg-background p-4 rounded-full mb-4">
        <Icon className="h-8 w-8 text-text-secondary" />
      </div>
      <h3 className="text-lg font-semibold text-text-primary mb-2">{title}</h3>
      <p className="text-sm text-text-secondary max-w-sm mb-6">{message}</p>
      {action && <div>{action}</div>}
    </div>
  );
}
