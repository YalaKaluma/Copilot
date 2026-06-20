import type { ExecutionLogEntry } from '../../hooks/useOrchestratorChat';
import { DISPLAY_NAMES } from './constants';
import type { ExecutionStep, TimelineItem } from './types';

export function formatValue(value: unknown) {
  if (value === null) return 'null';
  if (value === undefined) return '';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function formatDisplayName(name: string): string {
  if (DISPLAY_NAMES[name]) return DISPLAY_NAMES[name];
  return name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function normalizeSteps(rawSteps: (ExecutionStep | string)[] = []): ExecutionStep[] {
  return rawSteps.map((step, index) => {
    if (typeof step === 'object' && step !== null && 'name' in step) {
      return step as ExecutionStep;
    }
    return {
      id: `step-${index + 1}`,
      name: typeof step === 'string' ? step : String(step),
      status: 'pending' as const,
    };
  });
}

export function buildTimelineItems(executionLog: ExecutionLogEntry[]): TimelineItem[] {
  const items: TimelineItem[] = [];
  let currentSubAgent: { agent: string; entries: ExecutionLogEntry[] } | null = null;

  executionLog.forEach((entry) => {
    const agent = entry.agent || 'orchestrator';

    if (agent === 'orchestrator') {
      if (currentSubAgent) {
        items.push({ type: 'agent-group', ...currentSubAgent });
        currentSubAgent = null;
      }
      items.push({ type: 'entry', entry });
      return;
    }

    if (currentSubAgent && currentSubAgent.agent === agent) {
      currentSubAgent.entries.push(entry);
      return;
    }

    if (currentSubAgent) {
      items.push({ type: 'agent-group', ...currentSubAgent });
    }
    currentSubAgent = { agent, entries: [entry] };
  });

  if (currentSubAgent) {
    items.push({ type: 'agent-group', ...currentSubAgent });
  }

  return items;
}
