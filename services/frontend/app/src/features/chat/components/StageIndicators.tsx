import React from 'react';
import { Check, Circle, Loader2 } from 'lucide-react';
import { cn } from '../../../shared/utils/cn';
import { PIPELINE_STAGES, getStageBadgeLabel } from '../utils/stage';

export function StageBadge({ stage }: { stage: string | null }) {
  const stageColors: Record<string, string> = {
    scoping:
      'bg-sk-accent-blue/10 text-sk-accent-blue border-sk-accent-blue/20',
    planning:
      'bg-yellow-50 text-yellow-600 border-yellow-200 dark:bg-yellow-500/10 dark:text-yellow-400 dark:border-yellow-500/20',
    execution: 'bg-sk-accent-red/10 text-sk-accent-red border-sk-accent-red/20',
    waiting_for_info:
      'bg-orange-50 text-orange-600 border-orange-200 dark:bg-orange-500/10 dark:text-orange-400 dark:border-orange-500/20',
    done: 'bg-green-50 text-green-600 border-green-200 dark:bg-green-500/10 dark:text-green-400 dark:border-green-500/20',
  };

  if (!stage) return null;

  return (
    <span
      className={cn(
        'px-2 py-0.5 rounded-full text-[10px] font-medium border',
        stageColors[stage] ||
          'bg-gray-100 text-gray-500 border-gray-200 dark:bg-white/10 dark:text-gray-400 dark:border-white/10'
      )}
    >
      {getStageBadgeLabel(stage)}
    </span>
  );
}

export function StageProgress({
  currentStage,
  isWorkflowComplete = false,
}: {
  currentStage: string | null;
  isWorkflowComplete?: boolean;
}) {
  const isWaiting = currentStage === 'waiting_for_info';
  const resolvedStage = isWaiting ? null : currentStage;
  const currentIndex = resolvedStage
    ? PIPELINE_STAGES.indexOf(resolvedStage as (typeof PIPELINE_STAGES)[number])
    : -1;

  return (
    <div className="flex items-center gap-3">
      {PIPELINE_STAGES.map((stage, index) => {
        const isDoneStage = stage === 'done';
        const isCompleted = isDoneStage ? isWorkflowComplete : currentIndex > index;
        const isCurrent =
          !isWaiting && currentIndex === index && !(isDoneStage && isWorkflowComplete);
        const isPending = currentIndex < index;

        return (
          <React.Fragment key={stage}>
            <div className="flex items-center gap-1.5">
              {isCompleted ? (
                <div className="w-4.5 h-4.5 rounded-full bg-sk-accent-red flex items-center justify-center">
                  <Check className="w-3 h-3 text-white" strokeWidth={3} />
                </div>
              ) : isCurrent ? (
                <Loader2 className="w-4.5 h-4.5 text-sk-accent-red animate-spin" />
              ) : (
                <Circle className="w-4.5 h-4.5 text-gray-400" />
              )}
              <span
                className={cn(
                  'text-xs font-medium capitalize text-sk-text',
                  isPending && '!text-gray-400'
                )}
              >
                {stage}
              </span>
            </div>
            {index < PIPELINE_STAGES.length - 1 && (
              <div
                className={cn(
                  'w-6 h-px',
                  isCompleted ? 'bg-sk-accent-red' : 'bg-gray-300 dark:bg-white/20'
                )}
              />
            )}
          </React.Fragment>
        );
      })}
      {isWaiting && (
        <span className="text-xs font-medium text-orange-500 ml-1">Awaiting response</span>
      )}
    </div>
  );
}
