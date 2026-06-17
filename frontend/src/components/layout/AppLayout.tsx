import { useEffect, useState } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/useAuthStore';
import { LayoutDashboard, RadioReceiver, ShieldAlert, FileSearch, Network, Bell, BarChart2, LogOut, Moon, Sun, ChevronLeft, ChevronRight, Search, Menu, X, Users } from 'lucide-react';
import { cn } from '@/lib/utils';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { useAlertWebSocket } from '@/hooks/useAlertWebSocket';
import { userScopedStorage } from '@/lib/userScopedStorage';
import { CommandPalette, openCommandPalette } from '@/components/shared/CommandPalette';
import { UserBadge } from '@/components/shared/UserBadge';

interface ThemeStore {
  theme: 'light' | 'dark';
  toggleTheme: () => void;
}

const useThemeStore = create<ThemeStore>()(
  persist(
    (set) => ({
      theme: 'dark',
      toggleTheme: () => set((state) => ({ theme: state.theme === 'light' ? 'dark' : 'light' })),
    }),
    {
      name: 'theme-storage',
      storage: createJSONStorage(() => userScopedStorage),
    }
  )
);

interface SidebarStore {
  isCollapsed: boolean;
  toggleCollapsed: () => void;
}

const useSidebarStore = create<SidebarStore>()(
  persist(
    (set) => ({
      isCollapsed: false,
      toggleCollapsed: () => set((state) => ({ isCollapsed: !state.isCollapsed })),
    }),
    {
      name: 'sidebar-storage',
      storage: createJSONStorage(() => userScopedStorage),
    }
  )
);

const navItems = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'Threat Feed', path: '/feed', icon: ShieldAlert },
  { name: 'Channel Explorer', path: '/channels', icon: FileSearch },
  { name: 'Graph Visualizer', path: '/graph', icon: Network },
  { name: 'Alert Center', path: '/alerts', icon: Bell },
  { name: 'Analytics', path: '/analytics', icon: BarChart2 },
  { name: 'Sources Status', path: '/sources', icon: RadioReceiver, adminOnly: true },
  { name: 'Users', path: '/users', icon: Users, adminOnly: true },
];

export function AppLayout() {
  const logout = useAuthStore((state) => state.logout);
  const user = useAuthStore((state) => state.user);
  const location = useLocation();
  const { theme, toggleTheme } = useThemeStore();
  const { connectionStatus } = useAlertWebSocket();
  const { isCollapsed, toggleCollapsed } = useSidebarStore();
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <CommandPalette />
      {/* Mobile Backdrop */}
      {isMobileOpen && (
        <div 
          className="fixed inset-0 bg-background/80 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setIsMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <div className={cn(
        "fixed inset-y-0 left-0 z-50 lg:static border-r border-border bg-surface flex flex-col transition-transform duration-300 w-64 lg:transition-all lg:duration-300",
        isCollapsed ? "lg:w-16" : "lg:w-64",
        isMobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
      )}>
        <div className="h-16 flex items-center justify-between px-4 border-b border-border">
          {!isCollapsed && (
            <div className="flex items-center overflow-hidden">
              <ShieldAlert className="h-6 w-6 text-primary shrink-0 mr-2" />
              <span className="font-bold text-text-primary tracking-wide whitespace-nowrap">CTI Platform</span>
            </div>
          )}
          {isCollapsed && <ShieldAlert className="h-6 w-6 text-primary mx-auto hidden lg:block" />}
          <button 
            className="lg:hidden p-1.5 text-text-secondary hover:bg-border rounded-md"
            onClick={() => setIsMobileOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto py-4 overflow-x-hidden">
          <ul className="space-y-1 px-3">
            {navItems.filter(item => !item.adminOnly || user?.role === 'admin').map((item) => {
              const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path));
              const Icon = item.icon;
              return (
                <li key={item.path} title={isCollapsed ? item.name : undefined}>
                  <Link
                    to={item.path}
                    onClick={() => setIsMobileOpen(false)}
                    aria-label={isCollapsed ? item.name : undefined}
                    className={cn(
                      "flex items-center py-2 text-sm font-medium rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-surface",
                      isCollapsed ? "lg:justify-center lg:px-0 px-3" : "px-3",
                      isActive 
                        ? "bg-primary/10 text-primary border border-primary/20" 
                        : "text-text-secondary hover:bg-border/50 hover:text-text-primary border border-transparent"
                    )}
                  >
                    <Icon className={cn("h-5 w-5 shrink-0", !isCollapsed && "mr-3", isCollapsed && "lg:mr-0 mr-3", isActive ? "text-primary" : "text-text-secondary")} />
                    <span className={cn("truncate", isCollapsed && "lg:hidden")}>{item.name}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className={cn(
          "p-4 border-t border-border flex items-center",
          isCollapsed ? "lg:justify-center lg:flex-col lg:gap-4 justify-between" : "justify-between"
        )}>
          <button 
            onClick={toggleTheme}
            className="p-2 rounded-md hover:bg-border text-text-secondary transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-surface shrink-0"
            aria-label="Toggle dark mode"
          >
            {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>
          <button 
            onClick={logout}
            className={cn(
              "flex items-center text-sm font-medium rounded-md text-text-secondary hover:bg-critical/10 hover:text-critical transition-colors focus:outline-none focus:ring-2 focus:ring-critical focus:ring-offset-2 focus:ring-offset-surface",
              isCollapsed ? "p-2 justify-center" : "px-3 py-2"
            )}
            aria-label="Sign out"
            title={isCollapsed ? "Sign out" : undefined}
          >
            <LogOut className={cn("h-5 w-5 shrink-0", !isCollapsed && "mr-2", isCollapsed && "lg:mr-0 mr-2")} />
            <span className={cn(isCollapsed && "lg:hidden")}>Sign out</span>
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <header className="h-16 border-b border-border bg-surface flex items-center justify-between px-6 shrink-0">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setIsMobileOpen(true)}
              className="p-1.5 rounded-md text-text-secondary hover:bg-border transition-colors lg:hidden focus:outline-none focus:ring-2 focus:ring-primary"
              aria-label="Open sidebar menu"
            >
              <Menu className="h-5 w-5" />
            </button>
            <button
              onClick={toggleCollapsed}
              className="hidden lg:block p-1.5 rounded-md text-text-secondary hover:bg-border transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
              aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-expanded={!isCollapsed}
            >
              {isCollapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
            </button>
            <h1 className="text-xl font-semibold text-text-primary truncate">
              {navItems.find(i => location.pathname === i.path || (i.path !== '/' && location.pathname.startsWith(i.path)))?.name || 'Dashboard'}
            </h1>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider border flex items-center gap-1.5 ${connectionStatus === 'connected' ? 'bg-low/10 text-low border-low/20' : 'bg-critical/10 text-critical border-critical/20'}`} title={`WebSocket: ${connectionStatus}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${connectionStatus === 'connected' ? 'bg-low' : 'bg-critical animate-pulse'}`} />
              {connectionStatus === 'connected' ? 'LIVE' : 'DISCONNECTED'}
            </span>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={openCommandPalette}
              className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-background border border-border text-text-secondary text-sm hover:bg-surface hover:text-text-primary transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
              aria-label="Open search"
            >
              <Search className="h-4 w-4" />
              <span className="hidden sm:inline">Search</span>
              <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded border border-border bg-surface px-1.5 py-0.5 text-[10px] font-medium text-text-secondary">
                <span className="text-xs">⌘</span>K
              </kbd>
            </button>
            <UserBadge />
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6 bg-background" id="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
