import { useAppStore } from '@/store/appStore';
import { MoonIcon, SearchIcon, SunIcon } from 'lucide-react';
import { ConnectionIndicator } from './ConnectionIndicator';
import { NotificationCenter } from './NotificationCenter';

export function TopBar() {
  const { theme, setTheme } = useAppStore();

  return (
    <header className="h-16 bg-bg-secondary/70 backdrop-blur-xl border-b border-white/[0.06] px-6 flex items-center justify-between">
      {/* Search */}
      <div className="flex-1 max-w-xl">
        <div className="relative">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
          <input
            type="text"
            placeholder="Search projects..."
            className="w-full pl-10 pr-4 py-2 bg-bg-tertiary rounded-lg border border-border-subtle focus:border-accent-cyan focus:outline-none text-sm"
          />
        </div>
      </div>

      {/* Right actions */}
      <div className="flex items-center space-x-4">
        {/* Connection status */}
        <ConnectionIndicator />

        {/* Notifications */}
        <NotificationCenter />

        {/* Theme toggle */}
        <button
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          className="p-2 hover:bg-bg-hover rounded-lg transition-colors"
        >
          {theme === 'dark' ? (
            <MoonIcon className="w-5 h-5" />
          ) : (
            <SunIcon className="w-5 h-5" />
          )}
        </button>
      </div>
    </header>
  );
}
