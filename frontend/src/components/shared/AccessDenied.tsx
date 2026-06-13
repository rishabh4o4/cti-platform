import React from 'react';
import { ShieldAlert, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Role } from '../../types';

export function AccessDenied({ requiredRole }: { requiredRole?: Role }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-6 space-y-4">
      <ShieldAlert className="h-16 w-16 text-critical" />
      <h2 className="text-2xl font-semibold text-text-primary">Access Denied</h2>
      <p className="text-text-secondary max-w-md">
        You do not have the required permissions to view this content.
        {requiredRole && ` This area requires the ${requiredRole.toUpperCase()} role.`}
      </p>
      <Link
        to="/"
        className="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-surface border border-border text-text-primary rounded-md hover:bg-background transition-colors"
      >
        <ArrowLeft className="h-4 w-4" /> Return to Dashboard
      </Link>
    </div>
  );
}
