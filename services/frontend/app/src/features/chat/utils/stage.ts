export const PIPELINE_STAGES = ['scoping', 'planning', 'execution', 'done'] as const;

const STAGE_BADGE_LABELS: Record<string, string> = {
  execution: 'executing',
  waiting_for_info: 'Awaiting response',
};

export function getStageBadgeLabel(stage: string): string {
  return STAGE_BADGE_LABELS[stage] ?? stage;
}

export function getStageLoadingLabel(stage: string | null): string {
  if (!stage) return 'Thinking';
  switch (stage) {
    case 'scoping':
      return 'Scoping';
    case 'planning':
      return 'Planning';
    case 'execution':
      return 'Executing';
    case 'done':
      return 'Finalising';
    case 'waiting_for_info':
      return 'Awaiting response';
    default:
      return stage.charAt(0).toUpperCase() + stage.slice(1);
  }
}
