/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { useAuthStore } from '@/store/useAuthStore';
import { UserX, ShieldAlert, Plus, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { ErrorState } from '@/components/shared/ErrorState';
import { TableSkeleton } from '@/components/shared/Skeleton';

const fetchUsers = async () => (await api.get('/users')).data;

function getRelativeTime(dateString: string | null) {
  if (!dateString) return 'Never';
  const diff = Date.now() - new Date(dateString).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes} min${minutes > 1 ? 's' : ''} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr${hours > 1 ? 's' : ''} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days > 1 ? 's' : ''} ago`;
}

export default function UserManagement() {
  const user = useAuthStore((state) => state.user);
  const queryClient = useQueryClient();

  const { data: users, isLoading, isError, refetch } = useQuery({
    queryKey: ['users'],
    queryFn: fetchUsers,
  });

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('analyst');
  const [usernameError, setUsernameError] = useState('');
  const [passwordError, setPasswordError] = useState('');

  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({ isOpen: false, title: '', message: '', onConfirm: () => {} });

  const validateForm = () => {
    let isValid = true;
    setUsernameError('');
    setPasswordError('');

    if (!/^[a-zA-Z0-9_]{3,50}$/.test(newUsername)) {
      setUsernameError('Username must be 3-50 characters long and contain only letters, numbers, and underscores.');
      isValid = false;
    }
    if (newPassword.length < 8 || !/\d/.test(newPassword)) {
      setPasswordError('Password must be at least 8 characters long and contain at least one number.');
      isValid = false;
    }
    return isValid;
  };

  const createUserMutation = useMutation({
    mutationFn: async () => {
      return (await api.post('/users', { username: newUsername, password: newPassword, role: newRole, is_active: true })).data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('User created successfully');
      setIsCreateModalOpen(false);
      setNewUsername('');
      setNewPassword('');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create user');
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: async (userId: string) => {
      await api.delete(`/users/${userId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('User deactivated successfully');
    },
    onError: () => toast.error('Failed to deactivate user'),
  });

  const changeRoleMutation = useMutation({
    mutationFn: async ({ userId, role }: { userId: string, role: string }) => {
      await api.patch(`/users/${userId}/role`, { role });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('User role updated successfully');
    },
    onError: () => toast.error('Failed to update role'),
  });

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      createUserMutation.mutate();
    }
  };

  const confirmDeactivate = (userId: string, username: string) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Deactivate User',
      message: `Are you sure you want to deactivate ${username}? They will be immediately logged out of all sessions.`,
      onConfirm: () => {
        deactivateMutation.mutate(userId);
        setConfirmDialog(prev => ({ ...prev, isOpen: false }));
      }
    });
  };

  const confirmRoleChange = (userId: string, username: string, newRole: string) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Change User Role',
      message: `Are you sure you want to change ${username}'s role to ${newRole}? This will trigger immediate session invalidation.`,
      onConfirm: () => {
        changeRoleMutation.mutate({ userId, role: newRole });
        setConfirmDialog(prev => ({ ...prev, isOpen: false }));
      }
    });
  };

  if (user?.role !== 'admin') {
    return <ErrorState title="Access Denied" message="You do not have permission to view this page." />;
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-text-primary">User Management</h1>
        <button 
          onClick={() => setIsCreateModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background font-medium"
        >
          <Plus className="h-5 w-5" />
          Create User
        </button>
      </div>

      <div className="bg-surface border border-border rounded-xl shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-background border-b border-border">
              <tr>
                <th className="px-6 py-4 font-medium text-text-secondary">Username</th>
                <th className="px-6 py-4 font-medium text-text-secondary">Role</th>
                <th className="px-6 py-4 font-medium text-text-secondary">Status</th>
                <th className="px-6 py-4 font-medium text-text-secondary">Last Login</th>
                <th className="px-6 py-4 font-medium text-right text-text-secondary">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                <tr><td colSpan={5} className="p-6"><TableSkeleton cols={5} rows={5} /></td></tr>
              ) : isError ? (
                <tr><td colSpan={5} className="p-0"><ErrorState onRetry={refetch} className="rounded-none border-x-0 border-b-0" /></td></tr>
              ) : users?.map((u: any) => (
                <tr key={u.id} className="hover:bg-background/50 transition-colors">
                  <td className="px-6 py-4 text-text-primary font-medium">{u.username}</td>
                  <td className="px-6 py-4">
                    <select 
                      value={u.role}
                      onChange={(e) => confirmRoleChange(u.id, u.username, e.target.value)}
                      disabled={u.id === user.id || changeRoleMutation.isPending}
                      className="bg-background border border-border rounded-md text-sm px-2 py-1 focus:outline-none focus:ring-2 focus:ring-primary text-text-primary"
                    >
                      <option value="admin">Admin</option>
                      <option value="analyst">Analyst</option>
                      <option value="viewer">Viewer</option>
                    </select>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider ${u.is_active ? 'bg-low/10 text-low border border-low/20' : 'bg-critical/10 text-critical border border-critical/20'}`}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-text-secondary cursor-help" title={u.last_login ? new Date(u.last_login).toLocaleString() : 'Never logged in'}>
                    {getRelativeTime(u.last_login)}
                  </td>
                  <td className="px-6 py-4 text-right">
                    {u.is_active && u.id !== user.id && (
                      <button 
                        onClick={() => confirmDeactivate(u.id, u.username)}
                        className="inline-flex items-center justify-center p-2 rounded-md text-text-secondary hover:bg-critical/10 hover:text-critical transition-colors focus:outline-none focus:ring-2 focus:ring-critical"
                        title="Deactivate User"
                      >
                        <UserX className="h-4 w-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create User Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface border border-border rounded-xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="flex justify-between items-center p-6 border-b border-border">
              <h2 className="text-xl font-bold text-text-primary">Create New User</h2>
              <button onClick={() => setIsCreateModalOpen(false)} className="text-text-secondary hover:text-text-primary">
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleCreateSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Username</label>
                <input 
                  type="text"
                  value={newUsername}
                  onChange={(e) => { setNewUsername(e.target.value); setUsernameError(''); }}
                  className={`w-full bg-background border ${usernameError ? 'border-critical focus:ring-critical' : 'border-border focus:ring-primary'} rounded-md px-3 py-2 text-text-primary focus:outline-none focus:ring-2`}
                />
                {usernameError && <p className="text-critical text-xs mt-1">{usernameError}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Password</label>
                <input 
                  type="password"
                  value={newPassword}
                  onChange={(e) => { setNewPassword(e.target.value); setPasswordError(''); }}
                  className={`w-full bg-background border ${passwordError ? 'border-critical focus:ring-critical' : 'border-border focus:ring-primary'} rounded-md px-3 py-2 text-text-primary focus:outline-none focus:ring-2`}
                />
                {passwordError && <p className="text-critical text-xs mt-1">{passwordError}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Role</label>
                <select 
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  className="w-full bg-background border border-border rounded-md px-3 py-2 text-text-primary focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="admin">Admin</option>
                  <option value="analyst">Analyst</option>
                  <option value="viewer">Viewer</option>
                </select>
              </div>
              <div className="pt-4 flex justify-end gap-3">
                <button 
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-4 py-2 border border-border text-text-primary rounded-md hover:bg-background transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  disabled={createUserMutation.isPending}
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
                >
                  {createUserMutation.isPending ? 'Creating...' : 'Create User'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirmation Dialog */}
      {confirmDialog.isOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-[60] flex items-center justify-center p-4">
          <div className="bg-surface border border-border rounded-xl shadow-xl w-full max-w-md p-6">
            <h3 className="text-lg font-bold text-text-primary mb-2 flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-critical" />
              {confirmDialog.title}
            </h3>
            <p className="text-text-secondary mb-6">{confirmDialog.message}</p>
            <div className="flex justify-end gap-3">
              <button 
                onClick={() => setConfirmDialog(prev => ({ ...prev, isOpen: false }))}
                className="px-4 py-2 border border-border text-text-primary rounded-md hover:bg-background transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
              >
                Cancel
              </button>
              <button 
                onClick={confirmDialog.onConfirm}
                className="px-4 py-2 bg-critical text-critical-foreground rounded-md hover:bg-critical/90 transition-colors focus:outline-none focus:ring-2 focus:ring-critical"
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
