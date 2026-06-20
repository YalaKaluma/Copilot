import { ClerkProvider as ClerkReactProvider } from '@clerk/clerk-react';
import { ReactNode } from 'react';

interface ClerkProviderProps {
  children: ReactNode;
}

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

if (!PUBLISHABLE_KEY) {
  console.warn(
    'Missing Clerk publishable key. Add VITE_CLERK_PUBLISHABLE_KEY to your .env file.',
  );
}

export function ClerkProvider({ children }: ClerkProviderProps) {
  if (!PUBLISHABLE_KEY) {
    // Return app without Clerk if key is not configured
    return <>{children}</>;
  }

  return (
    <ClerkReactProvider publishableKey={PUBLISHABLE_KEY} afterSignOutUrl="/">
      {children}
    </ClerkReactProvider>
  );
}

export default ClerkProvider;