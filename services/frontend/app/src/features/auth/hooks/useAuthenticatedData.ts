import { useState, useCallback, DependencyList } from 'react';
import { useAuthenticatedEffect } from './useAuthenticatedEffect';

interface UseAuthenticatedDataOptions<T> {
  dataName: string;
  fetchFn: () => Promise<T>;
  deps?: DependencyList;
  defaultValue?: T;
  skip?: boolean;
}

interface UseAuthenticatedDataResult<T> {
  data: T | undefined;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

/**
 * A hook for fetching data that requires authentication.
 * Automatically handles loading states and errors.
 *
 * @param options - Configuration for the data fetching
 * @returns Object containing data, loading state, error, and refetch function
 */
export function useAuthenticatedData<T>({
  dataName,
  fetchFn,
  deps = [],
  defaultValue,
  skip = false,
}: UseAuthenticatedDataOptions<T>): UseAuthenticatedDataResult<T> {
  const [data, setData] = useState<T | undefined>(defaultValue);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (skip) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const result = await fetchFn();
      setData(result);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : `Failed to fetch ${dataName}`;
      setError(errorMessage);
      console.error(`Error fetching ${dataName}:`, err);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip, dataName, ...deps]);

  // Use authenticated effect to ensure auth is ready
  useAuthenticatedEffect(
    () => {
      fetchData();
    },
    [fetchData, ...deps],
    {
      onNotReady: () => {
        setLoading(false);
      },
    },
  );

  return {
    data,
    loading,
    error,
    refetch: fetchData,
  };
}

export default useAuthenticatedData;