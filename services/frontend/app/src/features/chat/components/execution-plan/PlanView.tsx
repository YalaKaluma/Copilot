import { memo } from 'react';
import { ListChecks, Target } from 'lucide-react';
import type { ExecutionPlan, ExecutionStep } from './types';
import { StepStatusIcon } from './StatusIcons';

interface PlanViewProps {
  plan: ExecutionPlan | null;
  steps: ExecutionStep[];
  completedSteps: number;
}

function PlanViewImpl({ plan, steps, completedSteps }: PlanViewProps) {
  return (
    <div className="p-4 space-y-3">
      {plan?.goal && (
        <div className="p-2.5 bg-sk-accent-red/5 rounded-lg border border-sk-accent-red/15">
          <div className="flex items-center gap-1.5 mb-0.5">
            <Target className="w-3 h-3 text-sk-accent-red" />
            <span className="text-[9px] font-medium text-sk-accent-red uppercase tracking-wider">Goal</span>
          </div>
          <p className="text-[11px] text-gray-600 dark:text-gray-300 leading-relaxed">{plan.goal}</p>
        </div>
      )}
      {steps.length > 0 ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2 mb-1">
            <ListChecks className="w-3.5 h-3.5 text-sk-accent-red" />
            <span className="text-xs font-semibold text-sk-text">Steps</span>
            <span className="text-[10px] text-gray-400 font-medium tabular-nums">
              {completedSteps}/{steps.length}
            </span>
          </div>
          {steps.map((step, index) => (
            <div
              key={step.id || index}
              style={{ borderLeftColor: 'rgba(200, 0, 65, 0.3)', borderLeftWidth: '2px' }}
              className="p-2 rounded-md bg-gray-50/50 dark:bg-white/5"
            >
              <div className="flex items-start gap-1.5">
                <div className="flex-shrink-0 mt-px">
                  <StepStatusIcon status={step.status} />
                </div>
                <span className="text-[11px] font-medium text-sk-text break-words leading-snug">{step.name}</span>
              </div>
              {step.description && (
                <p className="text-[10px] text-gray-500 mt-0.5 pl-[22px] line-clamp-2">{step.description}</p>
              )}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export const PlanView = memo(PlanViewImpl);
