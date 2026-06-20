import apiClient from '../../../shared/lib/api-client';
import type { FilterOptions } from '../types/filters.types';

/**
 * Fetches available filter options from the backend (SKAI get_filter_values).
 * Requires user to be connected to SKAI. Returns 401 if not connected, 502 if SKAI API fails.
 */
export async function fetchFilterOptions(skaiVersion?: string | null): Promise<FilterOptions> {
  return apiClient.get<FilterOptions>('/skai/filter-values', {
    params: skaiVersion ? { skai_version: skaiVersion } : undefined,
  });
}
