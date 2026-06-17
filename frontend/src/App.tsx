import React, { Suspense, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppLayout } from './components/layout/AppLayout';
import { ErrorBoundary } from './components/shared/ErrorBoundary';
import { Toaster } from 'react-hot-toast';

const Login = React.lazy(() => import('./pages/Login'));
const Dashboard = React.lazy(() => import('./pages/Dashboard'));
const ThreatFeed = React.lazy(() => import('./pages/ThreatFeed'));
const ChannelExplorer = React.lazy(() => import('./pages/ChannelExplorer'));
const InvestigationView = React.lazy(() => import('./pages/InvestigationView'));
const GraphVisualizer = React.lazy(() => import('./pages/GraphVisualizer'));
const AlertCenter = React.lazy(() => import('./pages/AlertCenter'));
const Analytics = React.lazy(() => import('./pages/Analytics'));
const SourceStatus = React.lazy(() => import('./pages/SourceStatus'));
const UserManagement = React.lazy(() => import('./pages/UserManagement'));
import { ProtectedRoute, RequireRole } from './components/shared/ProtectedRoute';
import { useAuthStore } from './store/useAuthStore';
import { fetchCurrentUser } from './lib/api';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);

  useEffect(() => {
    if (token && !user) {
      fetchCurrentUser().catch(() => {
        useAuthStore.getState().logout();
      });
    }
  }, [token, user]);

  if (token && !user) {
    return <div className="h-screen w-screen bg-background flex items-center justify-center text-text-secondary">Loading...</div>;
  }

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <Toaster position="top-right" toastOptions={{ className: 'bg-surface text-text-primary border border-border' }} />
        <BrowserRouter>
          <Suspense fallback={<div className="h-screen w-screen bg-background flex items-center justify-center text-text-secondary">Loading...</div>}>
            <Routes>
              <Route path="/login" element={<Login />} />
              
              <Route element={<ProtectedRoute />}>
                <Route element={<AppLayout />}>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/feed" element={<ThreatFeed />} />
                  <Route path="/channels" element={<ChannelExplorer />} />
                  <Route path="/investigation/:id" element={<InvestigationView />} />
                  <Route path="/graph" element={<GraphVisualizer />} />
                  <Route path="/alerts" element={<AlertCenter />} />
                  <Route path="/analytics" element={<Analytics />} />
                  <Route path="/sources" element={<RequireRole role="admin"><SourceStatus /></RequireRole>} />
                  <Route path="/users" element={<RequireRole role="admin"><UserManagement /></RequireRole>} />
                </Route>
              </Route>
              
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
