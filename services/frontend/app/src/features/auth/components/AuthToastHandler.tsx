import { ReactNode } from 'react';
import { useAuthToasts } from '../hooks/useAuthToasts';

interface AuthToastHandlerProps {
  children: ReactNode;
}

/**
 * Wrapper component that handles authentication-related toast notifications.
 * Should be placed inside ClerkProvider but outside of routing.
 */
export function AuthToastHandler({ children }: AuthToastHandlerProps) {
  // Initialize auth toasts
  useAuthToasts();

  return <>{children}</>;
}

export default AuthToastHandler;