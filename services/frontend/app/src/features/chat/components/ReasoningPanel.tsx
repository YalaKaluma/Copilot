import { useEffect, useRef, useState } from 'react';
import { ChevronDown, Loader2 } from 'lucide-react';
import { splitStatusSections } from '../utils/statusLines';
import { cn } from '../../../shared/utils/cn';

export interface ReasoningPanelProps {
  steps: string[];
  /** True when the AI is working but we're not receiving a live stream (e.g. rehydrated active chat). */
  isThinking?: boolean;
}

/** Inline markdown: **bold**, *italic*, `code`. */
function formatInline(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} className="font-semibold">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith('*') && part.endsWith('*') && !part.startsWith('**')) {
      return (
        <em key={i} className="italic opacity-80">
          {part.slice(1, -1)}
        </em>
      );
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={i}
          className="px-1.5 py-0.5 rounded bg-black/10 dark:bg-white/10 font-mono text-xs"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

export function ReasoningPanel({ steps, isThinking }: ReasoningPanelProps) {
  const [expanded, setExpanded] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const sections = splitStatusSections(steps);

  useEffect(() => {
    if (expanded && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [sections.length, expanded]);

  if (steps.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white p-6 text-center">
        {isThinking ? (
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-5 h-5 text-sk-accent-red animate-spin" />
            <p className="text-sm text-sk-contrast-grey">
              SKAI is thinking&hellip;
            </p>
          </div>
        ) : (
          <p className="text-sm text-sk-contrast-grey">
            Reasoning will appear here when the assistant thinks through the answer.
          </p>
        )}
      </div>
    );
  }

  if (sections.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white p-6 text-center">
        <p className="text-sm text-sk-contrast-grey">No reasoning steps for this reply.</p>
      </div>
    );
  }

  return (
    <div className="relative flex flex-col h-full bg-sk-white rounded-xl border border-gray-200 dark:border-white/10 shadow-sm text-sk-text overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex-shrink-0 flex items-center gap-1 px-4 py-2 text-[11px] text-gray-400 hover:text-gray-500 transition-colors cursor-pointer border-b border-gray-200 dark:border-white/10"
        aria-expanded={expanded}
      >
        <ChevronDown
          className={cn('w-3 h-3 transition-transform', !expanded && '-rotate-90')}
        />
        <span>
          {sections.length} {sections.length === 1 ? 'step' : 'steps'}
        </span>
      </button>
      {expanded && (
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto min-h-0 p-4 divide-y divide-gray-200 dark:divide-white/10"
        >
          {sections.map((section, i) => (
            <div key={i} className="py-2 first:pt-0 last:pb-0">
              <p className="text-[11px] text-gray-600 dark:text-gray-300 whitespace-pre-wrap leading-relaxed">
                {formatInline(section)}
              </p>
            </div>
          ))}
          {isThinking && (
            <div className="py-2 flex items-center gap-2 text-sk-contrast-grey">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span className="text-[11px]">Thinking&hellip;</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
