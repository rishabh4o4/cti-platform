import React from 'react';
import { Navigate, useLocation, Outlet } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
import { hasPermission } from '../../lib/rbac';
import { type Role, Permission } from '../../types';
import { AccessDenied } from './AccessDenied';

export function ProtectedRoute() {
  const token = useAuthStore((state) => state.token);
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}

export function RequireRole({ role, children }: { role: Role; children: React.ReactNode }) {
  const user = useAuthStore((state) => state.user);

  if (user?.role !== role) {
    return <AccessDenied requiredRole={role} />;
  }

  return <>{children}</>;
}

export function RequirePermission({ permission, children }: { permission: Permission; children: React.ReactNode }) {
  const user = useAuthStore((state) => state.user);

  if (!hasPermission(user?.role, permission)) {
    return <AccessDenied />;
  }

  return <>{children}</>;
}
