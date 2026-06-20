import { useState, useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import { LayoutTemplate, Plus } from 'lucide-react';
import { motion } from 'motion/react';
import { cn } from '../../../shared/utils/cn';
import type { TemplateListItem } from '../types/template.types';

export interface TemplateAutocompleteHandle {
  handleKeyDown: (e: React.KeyboardEvent) => boolean;
}

interface TemplateAutocompleteProps {
  templates: TemplateListItem[];
  filter: string;
  onSelect: (id: string) => void;
  onClose: () => void;
  onCreate: () => void;
}

export const TemplateAutocomplete = forwardRef<TemplateAutocompleteHandle, TemplateAutocompleteProps>(
  function TemplateAutocomplete({ templates, filter, onSelect, onClose, onCreate }, ref) {
    const [activeIndex, setActiveIndex] = useState(0);
    const listRef = useRef<HTMLDivElement>(null);

    const filtered = templates.filter((t) =>
      t.name.toLowerCase().includes(filter.toLowerCase())
    );

    // Extra item for "Create new template..."
    const totalItems = filtered.length + 1;

    // Reset active index when filter changes
    useEffect(() => {
      setActiveIndex(0);
    }, [filter]);

    // Scroll active item into view
    useEffect(() => {
      if (listRef.current) {
        const active = listRef.current.children[activeIndex] as HTMLElement | undefined;
        active?.scrollIntoView({ block: 'nearest' });
      }
    }, [activeIndex]);

    useImperativeHandle(ref, () => ({
      handleKeyDown(e: React.KeyboardEvent): boolean {
        switch (e.key) {
          case 'ArrowDown':
            e.preventDefault();
            setActiveIndex((prev) => (prev + 1) % totalItems);
            return true;
          case 'ArrowUp':
            e.preventDefault();
            setActiveIndex((prev) => (prev - 1 + totalItems) % totalItems);
            return true;
          case 'Enter':
            e.preventDefault();
            if (activeIndex < filtered.length) {
              onSelect(filtered[activeIndex].id);
            } else {
              onCreate();
            }
            return true;
          case 'Escape':
            e.preventDefault();
            onClose();
            return true;
          default:
            return false;
        }
      },
    }));

    return (
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 4 }}
        transition={{ duration: 0.1 }}
        className="absolute bottom-full left-0 right-0 mb-1 bg-sk-white rounded-xl border border-gray-200 dark:border-white/10 shadow-lg z-30 max-h-60 overflow-y-auto"
      >
        <div ref={listRef} className="py-1">
          {filtered.length === 0 && (
            <div className="px-4 py-3 text-xs text-gray-400">No matching templates</div>
          )}
          {filtered.map((tmpl, i) => (
            <div
              key={tmpl.id}
              className={cn(
                'flex items-center gap-2.5 px-4 py-2 text-sm cursor-pointer transition-colors',
                i === activeIndex ? 'bg-gray-50 dark:bg-white/5 text-sk-text' : 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-white/5'
              )}
              onClick={() => onSelect(tmpl.id)}
              onMouseEnter={() => setActiveIndex(i)}
            >
              <LayoutTemplate className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <span className="truncate block">{tmpl.name}</span>
                {tmpl.description && (
                  <span className="text-[11px] text-gray-400 truncate block">{tmpl.description}</span>
                )}
              </div>
            </div>
          ))}
          <div
            className={cn(
              'flex items-center gap-2.5 px-4 py-2 text-sm cursor-pointer transition-colors border-t border-gray-100 dark:border-white/10',
              activeIndex === filtered.length ? 'bg-gray-50 dark:bg-white/5 text-sk-accent-red' : 'text-gray-400 hover:bg-gray-50 dark:hover:bg-white/5 hover:text-sk-accent-red'
            )}
            onClick={onCreate}
            onMouseEnter={() => setActiveIndex(filtered.length)}
          >
            <Plus className="w-4 h-4 flex-shrink-0" />
            <span>Create new template...</span>
          </div>
        </div>
      </motion.div>
    );
  }
);
