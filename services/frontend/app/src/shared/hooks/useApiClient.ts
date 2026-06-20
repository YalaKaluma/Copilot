import { useAuth } from '@clerk/clerk-react';
import { useEffect } from 'react';
import { apiClient } from '../lib/api-client';

/**
 * Hook to initialize API client with Clerk authentication
 * Call this in your App component or root component
 */
export function useApiClient() {
  const { getToken } = useAuth();

  useEffect(() => {
    // Set up Clerk token getter for the API client
    apiClient.setClerkTokenGetter(async () => {
      try {
        // Force token refresh to avoid expired tokens
        return await getToken();
      } catch (error) {
        console.warn('Failed to get Clerk token:', error);
        return null;
      }
    });
  }, [getToken]);

  return apiClient;
}

export default useApiClient;