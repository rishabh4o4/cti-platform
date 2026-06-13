import { useAuthStore } from '../store/useAuthStore';
import { Permission, type Role } from '../types';

export const PERMISSION_MATRIX: Record<Role, Permission[]> = {
  admin: [
    Permission.VIEW_ALL,
    Permission.INVESTIGATE,
    Permission.ACKNOWLEDGE_ALERTS,
    Permission.ADD_NOTES,
    Permission.EXPORT_PDF,
    Permission.INGEST_CONTENT,
    Permission.TRIGGER_COLLECTION,
    Permission.MANAGE_USERS,
  ],
  analyst: [
    Permission.VIEW_ALL,
    Permission.INVESTIGATE,
    Permission.ACKNOWLEDGE_ALERTS,
    Permission.ADD_NOTES,
    Permission.EXPORT_PDF,
  ],
  viewer: [
    Permission.VIEW_ALL,
  ],
};

export function hasPermission(role: Role | undefined | null, permission: Permission): boolean {
  if (!role) return false;
  const permissions = PERMISSION_MATRIX[role] || [];
  return permissions.includes(permission);
}

export function usePermission(permission: Permission): boolean {
  const user = useAuthStore((state) => state.user);
  return hasPermission(user?.role, permission);
}

export function useRole(): Role | null {
  const user = useAuthStore((state) => state.user);
  return user?.role || null;
}

export function useReadOnlyMode(): boolean {
  const role = useRole();
  return role === 'viewer';
}
