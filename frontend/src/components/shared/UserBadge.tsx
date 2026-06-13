import React from 'react';
import { useAuthStore } from '../../store/useAuthStore';
import { Shield } from 'lucide-react';

export function UserBadge() {
  const user = useAuthStore((state) => state.user);

  if (!user) return null;

  const roleColors = {
    admin: 'bg-critical/10 text-critical border-critical/20',
    analyst: 'bg-primary/10 text-primary border-primary/20',
    viewer: 'bg-low/10 text-low border-low/20',
  };

  const roleColor = roleColors[user.role] || roleColors.viewer;

  return (
    <div className="flex items-center gap-3 pr-2">
      <div className="flex flex-col items-end">
        <span className="text-sm font-semibold text-text-primary leading-tight">{user.username}</span>
        <span className={`text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded border mt-0.5 ${roleColor}`}>
          {user.role}
        </span>
      </div>
      <div className="h-8 w-8 rounded-full bg-surface border border-border flex items-center justify-center shrink-0 shadow-sm">
        <Shield className="h-4 w-4 text-text-secondary" />
      </div>
    </div>
  );
}
