import { useMemo, useState } from 'react';
import { ChevronRight, ExternalLink } from 'lucide-react';
import type { ExecutionLogEntry } from '../hooks/useOrchestratorChat';
import { ExecutionTimelineView } from './execution-plan/ExecutionTimelineView';
import { PlanView } from './execution-plan/PlanView';
import type { ExecutionPlan, ExecutionStep, TimelineItem } from './execution-plan/types';
import { buildTimelineItems, normalizeSteps } from './execution-plan/utils';
import { formatDisplayName } from './execution-plan/utils';
import { config } from '../../../shared/lib/config';

interface ExecutionPlanPanelProps {
  plan: Record<string, unknown> | null;
  currentStage: string | null;
  isLoading: boolean;
  executionLog: ExecutionLogEntry[];
  sessionId?: string | null;
}

export function ExecutionPlanPanel({
  plan,
  currentStage: _currentStage,
  isLoading: _isLoading,
  executionLog,
  sessionId = null,
}: ExecutionPlanPanelProps) {
  const typedPlan = plan as ExecutionPlan | null;

  const steps = useMemo(() => normalizeSteps(typedPlan?.steps || []), [typedPlan?.steps]);
  const completedSteps = useMemo(
    () => steps.filter((step) => step.status === 'completed').length,
    [steps]
  );
  const timelineItems = useMemo(() => buildTimelineItems(executionLog), [executionLog]);
  const hasExecution = executionLog.length > 0;

  const agentNames = useMemo(
    () =>
      timelineItems
        .filter((item): item is Extract<TimelineItem, { type: 'agent-group' }> => item.type === 'agent-group')
        .map((item) => item.agent),
    [timelineItems]
  );

  const langfuseSessionUrl =
    config.langfuseTraceEnabled && config.langfuseProjectUrl && sessionId
      ? `${config.langfuseProjectUrl.replace(/\/$/, '')}/sessions/${sessionId}`
      : null;

  return (
    <PlanAndExecutionView
      typedPlan={typedPlan}
      steps={steps}
      completedSteps={completedSteps}
      hasExecution={hasExecution}
      timelineItems={timelineItems}
      agentNames={agentNames}
      langfuseSessionUrl={langfuseSessionUrl}
    />
  );
}

interface PlanAndExecutionViewProps {
  typedPlan: ExecutionPlan | null;
  steps: ExecutionStep[];
  completedSteps: number;
  hasExecution: boolean;
  timelineItems: TimelineItem[];
  agentNames: string[];
  langfuseSessionUrl: string | null;
}

function PlanAndExecutionView({
  typedPlan,
  steps,
  completedSteps,
  hasExecution,
  timelineItems,
  agentNames,
  langfuseSessionUrl,
}: PlanAndExecutionViewProps) {
  const [executionExpanded, setExecutionExpanded] = useState(true);

  return (
    <div className="relative flex flex-col h-full bg-sk-white rounded-xl border border-gray-200 dark:border-white/10 shadow-sm text-sk-text overflow-hidden">
      <div className="flex-1 overflow-y-auto min-h-0 flex flex-col">
        {langfuseSessionUrl && (
          <div className="flex-shrink-0 border-b border-gray-200 dark:border-white/10 px-4 py-2.5">
            <a
              href={langfuseSessionUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-sk-accent-red hover:underline"
            >
              <ExternalLink className="w-3.5 h-3.5 flex-shrink-0" />
              View in Langfuse
            </a>
          </div>
        )}
        <div className="flex-shrink-0">
          <PlanView plan={typedPlan} steps={steps} completedSteps={completedSteps} />
        </div>
        {!hasExecution && (
          <div className="flex-shrink-0 border-t border-gray-200 dark:border-white/10 px-4 py-3">
            <p className="text-[11px] text-sk-contrast-grey">
              Execution has not started yet. Traces will appear here once the query runs.
            </p>
          </div>
        )}
        {hasExecution && (
          <div className="flex-shrink-0 border-t border-gray-200 dark:border-white/10">
            <button
              type="button"
              onClick={() => setExecutionExpanded(!executionExpanded)}
              className="w-full flex items-center gap-2 px-4 py-2.5 text-left hover:bg-gray-50 dark:hover:bg-white/5 transition-colors cursor-pointer"
              aria-expanded={executionExpanded}
            >
              <ChevronRight
                className={`w-3.5 h-3.5 text-gray-400 transition-transform flex-shrink-0 ${executionExpanded ? 'rotate-90' : ''}`}
              />
              <span className="text-xs font-semibold text-sk-text">Agent execution</span>
              <span className="text-[10px] text-gray-400 font-medium tabular-nums ml-auto">
                {agentNames.length} {agentNames.length === 1 ? 'agent' : 'agents'}
              </span>
            </button>
            {executionExpanded && (
              <div className="px-4 pb-4">
                <div className="rounded-lg border border-gray-200 dark:border-white/10 overflow-hidden">
                  <ExecutionTimelineView items={timelineItems} />
                </div>
              </div>
            )}
            {!executionExpanded && agentNames.length > 0 && (
              <div className="px-4 pb-3 flex flex-wrap gap-1.5">
                {agentNames.map((name) => (
                  <span
                    key={name}
                    className="text-[10px] px-2 py-0.5 rounded bg-gray-100 dark:bg-white/10 text-gray-600 dark:text-gray-400"
                  >
                    {formatDisplayName(name)}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
