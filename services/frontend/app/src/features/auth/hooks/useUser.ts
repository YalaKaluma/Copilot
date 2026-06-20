import { useAuthenticatedData } from './useAuthenticatedData';
import { apiClient } from '../lib/api-client';

interface User {
  id: string;
  clerkUserId: string;
  preferredName?: string;
  initials?: string;
  role?: string;
  createdAt: string;
  updatedAt: string;
}

/**
 * Hook to fetch and manage the current user's data from the backend.
 * This complements Clerk's user data with application-specific user information.
 */
export function useUser() {
  const { data, loading, error, refetch } = useAuthenticatedData<User>({
    dataName: 'user',
    fetchFn: async () => {
      const response = await apiClient.get<User>('/api/users/me');
      return response;
    },
  });

  return {
    user: data,
    loading,
    error,
    refetch,
  };
}

export default useUser;