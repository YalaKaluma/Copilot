import { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { UserButton } from '@clerk/clerk-react';
import { Lock, LockOpen, ChevronDown, LogOut } from 'lucide-react';
import { apiClient } from '../../lib/api-client';

export function AppHeader() {
  const [skaiConnected, setSkaiConnected] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    apiClient
      .get<{ connected: boolean }>('/skai/auth/status')
      .then((data) => setSkaiConnected(data.connected))
      .catch(() => setSkaiConnected(false));

    const handleAuthChange = (e: Event) => {
      const detail = (e as CustomEvent<{ connected: boolean }>).detail;
      setSkaiConnected(detail.connected);
    };
    window.addEventListener('skai-auth-change', handleAuthChange);
    return () => window.removeEventListener('skai-auth-change', handleAuthChange);
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    if (!dropdownOpen) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [dropdownOpen]);

  const handleDisconnect = async () => {
    setIsDisconnecting(true);
    try {
      await apiClient.delete('/skai/auth/disconnect');
      window.dispatchEvent(new CustomEvent('skai-auth-change', { detail: { connected: false } }));
      setDropdownOpen(false);
    } catch {
      // silently fail — header is not the primary error surface
    } finally {
      setIsDisconnecting(false);
    }
  };

  return (
    <header className="w-full bg-sk-light-grey border-b border-gray-200 dark:border-white/10 py-3">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex items-center justify-between">
          {/* Logo Area */}
          <Link to="/" className="flex items-center gap-3">
            <img
              src="/sk-logo-small.png"
              alt="Simon Kucher"
              className="h-8 w-auto"
            />
            <span className="text-lg text-sk-text">
              <span className="font-semibold">SKAI</span>{' '}
              <span className="font-extralight">Growth Copilot</span>
            </span>
          </Link>

          {/* Right Area */}
          <div className="flex items-center gap-4">
            <div ref={dropdownRef} className="relative hidden sm:block">
              {skaiConnected ? (
                <button
                  type="button"
                  onClick={() => setDropdownOpen(!dropdownOpen)}
                  className={`inline-flex items-center gap-2 border border-gray-300 dark:border-white/10 bg-sk-white px-3 py-1.5 text-xs font-medium text-sk-text transition cursor-pointer ${dropdownOpen ? 'rounded-t-xl rounded-b-none border-b-0' : 'rounded-full'}`}
                >
                  {dropdownOpen ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <LockOpen className="h-4 w-4" />
                  )}
                  Connected to SKAI API
                </button>
              ) : (
                <span className="inline-flex items-center gap-2 rounded-full border border-gray-300 dark:border-white/10 bg-sk-white px-3 py-1.5 text-xs font-medium text-gray-400">
                  <Lock className="h-4 w-4" />
                  Not connected to SKAI
                </span>
              )}
              {dropdownOpen && skaiConnected && (
                <div className="absolute right-0 w-full rounded-b-xl border border-gray-300 dark:border-white/10 border-t-0 bg-sk-white shadow-md py-1.5 z-50">
                  <button
                    type="button"
                    onClick={handleDisconnect}
                    disabled={isDisconnecting}
                    className="flex items-center gap-2 w-full px-3 py-1.5 text-xs font-normal text-gray-500 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors cursor-pointer disabled:opacity-60"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    {isDisconnecting ? 'Disconnecting...' : 'Disconnect SKAI'}
                  </button>
                </div>
              )}
            </div>
            <UserButton
              appearance={{
                elements: {
                  avatarBox: "w-9 h-9"
                }
              }}
            />
          </div>
        </div>
      </div>
    </header>
  );
}

export default AppHeader;
