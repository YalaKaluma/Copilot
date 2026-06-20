import { memo } from 'react';
import type { TimelineItem } from './types';
import { DISPLAY_NAMES } from './constants';
import { ExecutionStatusIcon } from './StatusIcons';
import { SubAgentSection } from './SubAgentSection';
import { formatDisplayName, formatValue } from './utils';

interface ExecutionTimelineViewProps {
  items: TimelineItem[];
}

function ExecutionTimelineViewImpl({ items }: ExecutionTimelineViewProps) {
  return (
    <div className="p-4 space-y-2">
      {items.map((item, index) =>
        item.type === 'agent-group' ? (
          <SubAgentSection key={`${item.agent}-${index}`} agent={item.agent} entries={item.entries} />
        ) : (
          <div
            key={item.entry.id}
            style={{ borderLeftColor: 'rgba(200, 0, 65, 0.3)', borderLeftWidth: '3px' }}
            className="p-3 rounded-lg border border-gray-200 dark:border-white/10 bg-sk-white transition-all"
          >
            <div className="flex items-start gap-2">
              <div className="flex-shrink-0">
                <ExecutionStatusIcon status={item.entry.status} />
              </div>
              <span className="text-xs font-medium text-sk-text break-words">{formatDisplayName(item.entry.toolName)}</span>
            </div>
            <div className="pl-6">
              {item.entry.content && !DISPLAY_NAMES[item.entry.toolName] && (
                <p className="text-[11px] text-gray-500 mt-0.5">{item.entry.content}</p>
              )}
              {item.entry.args && Object.keys(item.entry.args).length > 0 && (
                <details className="mt-2">
                  <summary className="text-[10px] text-gray-500 cursor-pointer hover:text-sk-text transition-colors">
                    Input
                  </summary>
                  <pre className="mt-1 p-2 bg-gray-100 dark:bg-white/5 rounded text-[10px] text-gray-600 dark:text-gray-400 font-mono overflow-x-auto whitespace-pre-wrap">
                    {formatValue(item.entry.args)}
                  </pre>
                </details>
              )}
              {item.entry.result !== undefined && (
                <details className="mt-2">
                  <summary className="text-[10px] text-gray-500 cursor-pointer hover:text-sk-text transition-colors">
                    Output
                  </summary>
                  <pre className="mt-1 p-2 bg-gray-100 dark:bg-white/5 rounded text-[10px] text-gray-600 dark:text-gray-400 font-mono overflow-x-auto whitespace-pre-wrap">
                    {formatValue(item.entry.result)}
                  </pre>
                </details>
              )}
            </div>
          </div>
        )
      )}
    </div>
  );
}

export const ExecutionTimelineView = memo(ExecutionTimelineViewImpl);
