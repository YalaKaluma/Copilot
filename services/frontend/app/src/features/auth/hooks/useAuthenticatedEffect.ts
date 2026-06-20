import { DependencyList, useEffect } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { apiClient } from '../lib/api-client';

interface AuthenticatedEffectOptions {
  onNotReady?: () => void;
  skipAuthCheck?: boolean;
}

/**
 * A hook that runs an effect only when authentication is ready.
 * This prevents race conditions and ensures the API client is properly initialized.
 *
 * @param effect - The effect function to run when authenticated
 * @param deps - Dependency list for the effect
 * @param options - Optional configuration
 */
export function useAuthenticatedEffect(
  effect: () => void | (() => void),
  deps: DependencyList,
  options?: AuthenticatedEffectOptions,
) {
  const { isLoaded, isSignedIn } = useAuth();

  useEffect(() => {
    // Skip auth check if explicitly requested
    if (options?.skipAuthCheck) {
      return effect();
    }

    // Check if authentication is ready
    if (!isLoaded || !isSignedIn || !apiClient.isReady) {
      options?.onNotReady?.();
      return;
    }

    // Authentication is ready, run the effect
    return effect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoaded, isSignedIn, ...deps]);
}

export default useAuthenticatedEffect;