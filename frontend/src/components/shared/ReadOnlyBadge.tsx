
import { Eye } from 'lucide-react';
import { useReadOnlyMode } from '../../lib/rbac';

export function ReadOnlyBadge() {
  const isReadOnly = useReadOnlyMode();

  if (!isReadOnly) return null;

  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-low/10 text-low border border-low/20 rounded-md" title="You have view-only access.">
      <Eye className="h-3.5 w-3.5" />
      <span>Read Only</span>
    </div>
  );
}
