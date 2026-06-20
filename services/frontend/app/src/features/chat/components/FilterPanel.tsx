import { useState, useRef, useEffect } from 'react';
import { ChevronDown, HelpCircle, Loader2, X } from 'lucide-react';
import { cn } from '../../../shared/utils/cn';
import type { FilterOptions, SelectedFilters } from '../types/filters.types';

export interface FilterPanelProps {
  filterOptions: FilterOptions;
  filterOptionsLoading: boolean;
  selectedFilters: SelectedFilters;
  onToggleFilter: (key: string, value: string) => void;
  onClearFilters: () => void;
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
}

function hasAnySelection(selected: SelectedFilters): boolean {
  return Object.values(selected).some((arr) => arr.length > 0);
}

interface FilterDropdownProps {
  label: string;
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
}

function FilterDropdown({ label, options, selected, onToggle }: FilterDropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const summary =
    selected.length === 0 ? 'All' : selected.length === 1 ? selected[0] : `${selected.length} selected`;

  return (
    <div ref={ref} className="relative">
      <p className="text-xs font-medium uppercase tracking-wider text-sk-contrast-grey mb-1.5">
        {label}
      </p>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-sm text-left text-sk-text bg-white/5 border border-gray-200 dark:border-white/20 rounded-lg hover:bg-white/10 transition-colors cursor-pointer"
      >
        <span className="truncate">{summary}</span>
        <ChevronDown
          className={cn('w-4 h-4 flex-shrink-0 transition-transform', open && 'rotate-180')}
        />
      </button>
      {open && (
        <div className="absolute left-0 right-0 top-full z-10 mt-1 py-1 bg-sk-light-grey border border-gray-200 dark:border-white/20 rounded-lg shadow-lg max-h-48 overflow-y-auto">
          {options.map((value) => {
            const isSelected = selected.includes(value);
            return (
              <label
                key={value}
                className={cn(
                  'flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-white/10',
                  isSelected && 'bg-sk-accent-red/10 text-sk-text'
                )}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => onToggle(value)}
                  className="rounded border-gray-300 dark:border-white/30 text-sk-accent-red focus:ring-sk-accent-red"
                />
                <span className="truncate">{value}</span>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function FilterPanel({
  filterOptions,
  filterOptionsLoading,
  selectedFilters,
  onToggleFilter,
  onClearFilters,
  collapsed,
  onCollapsedChange,
}: FilterPanelProps) {
  const keys = Object.keys(filterOptions);
  const showClear = hasAnySelection(selectedFilters);

  return (
    <div className="mt-4 pt-4 flex flex-col min-h-0 border-t border-gray-200 dark:border-white/10 flex-shrink-0">
      <button
        type="button"
        onClick={() => onCollapsedChange(!collapsed)}
        className="flex items-center justify-between w-full px-3 py-2 text-sm font-medium uppercase tracking-wider text-sk-contrast-grey hover:text-sk-text transition-colors cursor-pointer flex-shrink-0"
      >
        <span className="flex items-center gap-2">
          Show filters
          <span
            className="inline-flex text-sk-contrast-grey hover:text-sk-text cursor-help"
            title="Filters will be applied only to new queries."
            onClick={(e) => e.stopPropagation()}
            aria-label="Filters will be applied only to new queries."
          >
            <HelpCircle className="w-3.5 h-3.5 flex-shrink-0" />
          </span>
          {filterOptionsLoading && (
            <Loader2 className="w-3.5 h-3.5 text-sk-contrast-grey animate-spin flex-shrink-0" aria-hidden />
          )}
        </span>
        <ChevronDown
          className={cn(
            'w-4 h-4 flex-shrink-0 transition-transform',
            !collapsed && 'rotate-180'
          )}
        />
      </button>
      {!collapsed && (
        <div className="overflow-y-auto min-h-0 mt-1 flex flex-col gap-3 py-1">
          {filterOptionsLoading && keys.length === 0 ? (
            <div className="flex justify-center py-4">
              <Loader2 className="w-5 h-5 text-sk-contrast-grey animate-spin" />
            </div>
          ) : keys.length === 0 ? (
            <p className="px-3 py-2 text-xs text-sk-contrast-grey">No filter options available.</p>
          ) : (
            <>
              {keys.map((key) => (
                <div key={key} className="px-3">
                  <FilterDropdown
                    label={key}
                    options={filterOptions[key] ?? []}
                    selected={selectedFilters[key] ?? []}
                    onToggle={(value) => onToggleFilter(key, value)}
                  />
                </div>
              ))}
              {showClear && (
                <button
                  type="button"
                  onClick={onClearFilters}
                  className="flex items-center justify-center gap-1.5 mx-3 mt-1 px-3 py-2 text-xs font-medium text-sk-contrast-grey hover:text-sk-text hover:bg-white/5 rounded-lg transition-colors cursor-pointer border border-gray-200 dark:border-white/10"
                >
                  <X className="w-3.5 h-3.5" />
                  Clear filters
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
