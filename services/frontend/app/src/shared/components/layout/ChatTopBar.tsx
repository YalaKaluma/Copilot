import { useEffect, useRef, useState } from 'react';
import { useUser } from '@clerk/clerk-react';
import { Link } from 'react-router-dom';
import { Lock, LockOpen, ChevronDown, Download, LogOut, User, Moon, Sun, Tag, FolderOpen } from 'lucide-react';
import { apiClient } from '../../lib/api-client';
import { cn } from '../../utils/cn';
import { useTheme } from '../../providers/ThemeProvider';

export interface ChatTopBarProps {
  skaiConnected: boolean;
  onSkaiAuthChange: () => void;
  /** When true, show version selector (dev/staging only; disabled in prod). */
  versionSelectorEnabled?: boolean;
  /** Available copilot version ids for the dropdown. */
  versions?: string[];
  /** Currently selected version id, or null for backend default. */
  selectedVersion?: string | null;
  /** Called when user selects a version. */
  onVersionChange?: (version: string | null) => void;
  /** When set, show the active project (chat scoped to this project). */
  activeProject?: { id: string; name: string };
  feedbackSessionId?: string | null;
}

export function ChatTopBar({
  skaiConnected,
  onSkaiAuthChange,
  versionSelectorEnabled = false,
  versions = [],
  selectedVersion = null,
  onVersionChange,
  activeProject,
  feedbackSessionId,
}: ChatTopBarProps) {
  const { user } = useUser();
  const { resolvedTheme, setTheme } = useTheme();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [versionDropdownOpen, setVersionDropdownOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [tenants, setTenants] = useState<string[]>([]);
  const [selectedTenant, setSelectedTenant] = useState(
    () => window.localStorage.getItem('skaiTenantCode') ?? ''
  );
  const [isDownloadingFeedback, setIsDownloadingFeedback] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const versionDropdownRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleAuthChange = (e: Event) => {
      const detail = (e as CustomEvent<{ connected: boolean }>).detail;
      if (!detail.connected) setDropdownOpen(false);
    };
    window.addEventListener('skai-auth-change', handleAuthChange);
    return () => window.removeEventListener('skai-auth-change', handleAuthChange);
  }, []);

  useEffect(() => {
    if (!skaiConnected) {
      setTenants([]);
      return;
    }
    apiClient
      .get<{ tenants: string[] }>('/skai/auth/tenants')
      .then(({ tenants: available }) => {
        setTenants(available ?? []);
        const current = window.localStorage.getItem('skaiTenantCode') ?? '';
        if (current && available.includes(current)) {
          setSelectedTenant(current);
        } else if (available.length > 0) {
          setSelectedTenant(available[0]);
          window.localStorage.setItem('skaiTenantCode', available[0]);
        }
      })
      .catch(() => setTenants([]));
  }, [skaiConnected]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
      if (versionDropdownRef.current && !versionDropdownRef.current.contains(e.target as Node)) {
        setVersionDropdownOpen(false);
      }
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [dropdownOpen, versionDropdownOpen, userMenuOpen]);

  const handleDisconnect = async () => {
    setIsDisconnecting(true);
    try {
      await apiClient.delete('/skai/auth/disconnect');
      window.localStorage.removeItem('skaiTenantCode');
      setSelectedTenant('');
      setTenants([]);
      window.dispatchEvent(new CustomEvent('skai-auth-change', { detail: { connected: false } }));
      setDropdownOpen(false);
      onSkaiAuthChange();
    } catch {
      // silently fail
    } finally {
      setIsDisconnecting(false);
    }
  };

  const handleFeedbackDownload = async () => {
    if (!feedbackSessionId) return;
    setIsDownloadingFeedback(true);
    try {
      const blob = await apiClient.getBlob(
        `/conversations/session/${feedbackSessionId}/feedback-workbook`
      );
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `growth-copilot-feedback-${feedbackSessionId}.xlsx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } finally {
      setIsDownloadingFeedback(false);
    }
  };

  return (
    <header className="flex-shrink-0 h-14 flex items-center justify-between px-4 border-b border-gray-200 dark:border-white/10 bg-sk-light-grey">
      {/* Active project pill (left) */}
      <div className="flex items-center min-w-0">
        {activeProject ? (
          <Link
            to={`/chat/projects/${activeProject.id}`}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium text-sk-accent-red bg-sk-accent-red/10 hover:bg-sk-accent-red/15 transition-colors truncate max-w-[220px]"
            title={`Chat in project: ${activeProject.name}`}
          >
            <FolderOpen className="h-4 w-4 flex-shrink-0" />
            <span className="truncate">{activeProject.name}</span>
          </Link>
        ) : null}
      </div>
      {/* Version selector (dev/staging) + connection status + user profile */}
      <div className="flex items-center gap-3">
        {feedbackSessionId && (
          <button
            type="button"
            onClick={handleFeedbackDownload}
            disabled={isDownloadingFeedback}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-sk-contrast-grey hover:text-sk-text disabled:opacity-50"
            title="Download conversation feedback workbook"
          >
            <Download className="h-4 w-4" />
            <span className="hidden xl:inline">
              {isDownloadingFeedback ? 'Preparing…' : 'Feedback XLSX'}
            </span>
          </button>
        )}
        {skaiConnected && tenants.length > 0 && (
          <label className="flex items-center gap-2 text-xs text-sk-contrast-grey">
            <span className="hidden xl:inline">Workspace</span>
            <select
              value={selectedTenant}
              onChange={(event) => {
                const tenant = event.target.value;
                setSelectedTenant(tenant);
                window.localStorage.setItem('skaiTenantCode', tenant);
                window.dispatchEvent(
                  new CustomEvent('skai-tenant-change', { detail: { tenant } })
                );
              }}
              className="rounded-md border border-gray-400/60 dark:border-white/20 bg-sk-white px-2 py-1.5 text-xs text-sk-text outline-none focus:border-sk-accent-red"
              aria-label="SKAI workspace"
            >
              {tenants.map((tenant) => (
                <option key={tenant} value={tenant}>{tenant}</option>
              ))}
            </select>
          </label>
        )}
        {/* Version selector: only visible when versionSelectorEnabled (non-prod); hidden in prod */}
        {versionSelectorEnabled && (
          <div ref={versionDropdownRef} className="relative">
            <button
              type="button"
              onClick={() => setVersionDropdownOpen(!versionDropdownOpen)}
              className={cn(
                'inline-flex items-center gap-2 text-xs font-medium transition cursor-pointer',
                'text-sk-contrast-grey hover:text-sk-text',
                versionDropdownOpen ? 'opacity-90' : ''
              )}
              aria-label="Skai version"
            >
              <Tag className="h-4 w-4" />
              {selectedVersion ?? 'default'}
              <ChevronDown className="h-4 w-4" />
            </button>
            {versionDropdownOpen && (
              <div className="absolute right-0 top-full mt-1 rounded-lg border border-gray-200 dark:border-white/10 bg-sk-white shadow-lg py-1 min-w-[120px] z-50">
                <button
                  type="button"
                  onClick={() => {
                    onVersionChange?.(null);
                    setVersionDropdownOpen(false);
                  }}
                  className={cn(
                    'flex w-full px-3 py-2 text-xs text-left transition-colors cursor-pointer',
                    selectedVersion === null
                      ? 'bg-sk-accent-red/10 text-sk-accent-red font-medium'
                      : 'text-sk-contrast-grey hover:bg-white/5 hover:text-sk-text'
                  )}
                >
                  default
                </button>
                {versions.map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => {
                      onVersionChange?.(v);
                      setVersionDropdownOpen(false);
                    }}
                    className={cn(
                      'flex w-full px-3 py-2 text-xs text-left transition-colors cursor-pointer',
                      selectedVersion === v
                        ? 'bg-sk-accent-red/10 text-sk-accent-red font-medium'
                        : 'text-sk-contrast-grey hover:bg-white/5 hover:text-sk-text'
                    )}
                  >
                    {v}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <div ref={dropdownRef} className="relative">
          {skaiConnected ? (
            <button
              type="button"
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className={cn(
                'inline-flex items-center gap-2 text-xs font-medium transition cursor-pointer',
                'text-sk-connected',
                dropdownOpen ? 'opacity-90' : 'hover:opacity-90'
              )}
            >
              {dropdownOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <LockOpen className="h-4 w-4" />
              )}
              Connected to SKAI API
            </button>
          ) : (
            <span className="inline-flex items-center gap-2 text-xs font-medium text-sk-contrast-grey">
              <Lock className="h-4 w-4" />
              Not connected to SKAI
            </span>
          )}
          {dropdownOpen && skaiConnected && (
            <div className="absolute left-0 top-full mt-1 rounded-lg border border-gray-200 dark:border-white/10 bg-sk-white shadow-lg py-1 min-w-[140px] z-50">
              <button
                type="button"
                onClick={handleDisconnect}
                disabled={isDisconnecting}
                className="flex items-center gap-2 w-full px-3 py-2 text-xs text-sk-contrast-grey hover:bg-white/5 hover:text-sk-text transition-colors cursor-pointer disabled:opacity-60"
              >
                <LogOut className="h-3.5 w-3.5" />
                {isDisconnecting ? 'Disconnecting...' : 'Disconnect SKAI'}
              </button>
            </div>
          )}
        </div>

        {/* User menu - avatar with dropdown, next to connection label */}
        <div className="relative" ref={userMenuRef}>
        <button
          type="button"
          onClick={() => setUserMenuOpen(!userMenuOpen)}
          className="w-9 h-9 rounded-full overflow-hidden border border-gray-200 dark:border-white/10 bg-sk-white flex items-center justify-center text-sk-text cursor-pointer hover:opacity-90 transition-opacity"
          aria-label="User menu"
        >
          {user?.imageUrl ? (
            <img src={user.imageUrl} alt="" className="w-full h-full object-cover" />
          ) : (
            <User className="w-5 h-5 text-sk-contrast-grey" />
          )}
        </button>
        {userMenuOpen && (
          <div className="absolute right-0 top-full mt-1 rounded-lg border border-gray-200 dark:border-white/10 bg-sk-white shadow-lg py-1 min-w-[180px] z-50">
            <Link
              to="/user"
              onClick={() => setUserMenuOpen(false)}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-sk-contrast-grey hover:bg-white/5 hover:text-sk-text transition-colors cursor-pointer"
            >
              <User className="w-4 h-4 flex-shrink-0" />
              Manage account
            </Link>
            <button
              type="button"
              onClick={() => {
                setTheme(resolvedTheme === 'dark' ? 'light' : 'dark');
              }}
              className="flex items-center justify-between w-full px-3 py-2 text-sm text-sk-contrast-grey hover:bg-white/5 hover:text-sk-text transition-colors cursor-pointer text-left"
            >
              <span className="flex items-center gap-2">
                {resolvedTheme === 'dark' ? (
                  <Sun className="w-4 h-4 flex-shrink-0" />
                ) : (
                  <Moon className="w-4 h-4 flex-shrink-0" />
                )}
                {resolvedTheme === 'dark' ? 'Light mode' : 'Dark mode'}
              </span>
            </button>
          </div>
        )}
        </div>
      </div>
    </header>
  );
}
