import { memo, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Bot, ChevronRight, Loader2 } from 'lucide-react';
import type { ExecutionLogEntry } from '../../hooks/useOrchestratorChat';
import { ExecutionStatusIcon } from './StatusIcons';
import { formatDisplayName, formatValue } from './utils';

interface SubAgentSectionProps {
  agent: string;
  entries: ExecutionLogEntry[];
}

function SubAgentSectionImpl({ agent, entries }: SubAgentSectionProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const completedCount = entries.filter((e) => e.status === 'completed').length;
  const isRunning = entries.some((e) => e.status === 'running');

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 hover:bg-gray-100 dark:hover:bg-white/10 transition-colors cursor-pointer"
      >
        <motion.div
          animate={{ rotate: isExpanded ? 90 : 0 }}
          transition={{ duration: 0.15 }}
          className="flex-shrink-0"
        >
          <ChevronRight className="w-3 h-3 text-gray-400" />
        </motion.div>

        {isRunning ? (
          <Loader2 className="w-3.5 h-3.5 text-sk-accent-red animate-spin flex-shrink-0" />
        ) : (
          <Bot className="w-3.5 h-3.5 text-sk-accent-red flex-shrink-0" />
        )}

        <span className="text-[11px] font-semibold text-sk-text">{formatDisplayName(agent)}</span>

        <span className="ml-auto text-[10px] text-gray-400 font-medium tabular-nums">
          {completedCount}/{entries.length}
        </span>
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
          >
            <div className="ml-4 pl-3 mt-1.5 space-y-1.5 border-l-2 border-sk-accent-red/15">
              {entries.map((entry) => {
                const hasArgs = entry.args && Object.keys(entry.args).length > 0;
                const hasResult = entry.result !== undefined;

                return (
                  <div
                    key={entry.id}
                    className="p-2 rounded-md border border-gray-100 dark:border-white/10 bg-sk-white"
                  >
                    <div className="flex items-start gap-1.5">
                      <div className="flex-shrink-0 mt-px">
                        <ExecutionStatusIcon status={entry.status} />
                      </div>
                      <span className="text-[11px] font-medium text-sk-text break-words">{entry.toolName}</span>
                    </div>
                    {(hasArgs || hasResult) && (
                      <div className="pl-[22px]">
                        {hasArgs && (
                          <details className="mt-1.5">
                            <summary className="text-[9px] text-gray-400 cursor-pointer hover:text-sk-text transition-colors">
                              Input
                            </summary>
                            <pre className="mt-1 p-1.5 bg-gray-50 dark:bg-white/5 rounded text-[9px] text-gray-500 font-mono overflow-x-auto whitespace-pre-wrap">
                              {formatValue(entry.args)}
                            </pre>
                          </details>
                        )}
                        {hasResult && (
                          <details className="mt-1.5">
                            <summary className="text-[9px] text-gray-400 cursor-pointer hover:text-sk-text transition-colors">
                              Output
                            </summary>
                            <pre className="mt-1 p-1.5 bg-gray-50 dark:bg-white/5 rounded text-[9px] text-gray-500 font-mono overflow-x-auto whitespace-pre-wrap">
                              {formatValue(entry.result)}
                            </pre>
                          </details>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export const SubAgentSection = memo(SubAgentSectionImpl);
