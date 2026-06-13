import { AlertCircle, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({ 
  title = 'Something went wrong', 
  message = 'We encountered an error while fetching the data. Please try again.',
  onRetry,
  className
}: ErrorStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center p-8 text-center bg-critical/5 border border-critical/20 rounded-xl', className)}>
      <AlertCircle className="h-10 w-10 text-critical mb-4" />
      <h3 className="text-lg font-semibold text-text-primary mb-2">{title}</h3>
      <p className="text-sm text-text-secondary max-w-sm mb-6">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center px-4 py-2 bg-background border border-border rounded-md text-sm font-medium text-text-primary hover:bg-surface focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background transition-colors"
        >
          <RefreshCw className="h-4 w-4 mr-2" />
          Retry
        </button>
      )}
    </div>
  );
}
