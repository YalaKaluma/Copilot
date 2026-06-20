import { useState, useCallback, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { fetchFilterOptions } from '../services/filterOptionsService';
import type { FilterOptions, SelectedFilters } from '../types/filters.types';

export interface UseFilterOptionsReturn {
  filterOptions: FilterOptions;
  filterOptionsLoading: boolean;
  selectedFilters: SelectedFilters;
  toggleFilter: (key: string, value: string) => void;
  clearFilters: () => void;
  filtersSectionCollapsed: boolean;
  setFiltersSectionCollapsed: (collapsed: boolean) => void;
}

export function useFilterOptions(skaiVersion?: string | null): UseFilterOptionsReturn {
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({});
  const [filterOptionsLoading, setFilterOptionsLoading] = useState(true);
  const [selectedFilters, setSelectedFilters] = useState<SelectedFilters>({});
  const [filtersSectionCollapsed, setFiltersSectionCollapsed] = useState(true);
  const filterOptionsRef = useRef<FilterOptions>({});

  const loadFilterOptions = useCallback(() => {
    setFilterOptionsLoading(true);
    fetchFilterOptions(skaiVersion)
      .then((data) => {
        setFilterOptions(data);
      })
      .catch(() => {
        toast.error('Failed to load filters');
      })
      .finally(() => {
        setFilterOptionsLoading(false);
      });
  }, [skaiVersion]);

  useEffect(() => {
    let cancelled = false;
    setFilterOptionsLoading(true);
    setSelectedFilters({});
    setFilterOptions({});
    fetchFilterOptions(skaiVersion)
      .then((data) => {
        if (!cancelled) {
          setFilterOptions(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          toast.error('Failed to load filters');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setFilterOptionsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [skaiVersion]);

  filterOptionsRef.current = filterOptions;

  // Refetch when SKAI auth state changes if we don't have filter options yet
  useEffect(() => {
    const handleSkaiAuthChange = () => {
      const hasOptions = Object.keys(filterOptionsRef.current).length > 0;
      if (!hasOptions) {
        loadFilterOptions();
      }
    };
    window.addEventListener('skai-auth-change', handleSkaiAuthChange);
    return () => window.removeEventListener('skai-auth-change', handleSkaiAuthChange);
  }, [loadFilterOptions]);

  const toggleFilter = useCallback((key: string, value: string) => {
    setSelectedFilters((prev) => {
      const current = prev[key] ?? [];
      const has = current.includes(value);
      const next = has ? current.filter((v) => v !== value) : [...current, value];
      if (next.length === 0) {
        const { [key]: _, ...rest } = prev;
        return rest;
      }
      return { ...prev, [key]: next };
    });
  }, []);

  const clearFilters = useCallback(() => {
    setSelectedFilters({});
  }, []);

  return {
    filterOptions,
    filterOptionsLoading,
    selectedFilters,
    toggleFilter,
    clearFilters,
    filtersSectionCollapsed,
    setFiltersSectionCollapsed,
  };
}
