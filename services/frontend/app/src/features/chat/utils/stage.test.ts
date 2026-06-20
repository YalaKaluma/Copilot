import { describe, expect, it } from 'vitest';
import { getStageBadgeLabel, getStageLoadingLabel } from './stage';

describe('stage utils', () => {
  it('maps execution stage to executing for badge labels', () => {
    expect(getStageBadgeLabel('execution')).toBe('executing');
  });

  it('maps waiting stage to Awaiting response for badge labels', () => {
    expect(getStageBadgeLabel('waiting_for_info')).toBe('Awaiting response');
  });

  it('maps loading labels for known stages', () => {
    expect(getStageLoadingLabel('execution')).toBe('Executing');
    expect(getStageLoadingLabel('waiting_for_info')).toBe('Awaiting response');
  });
});
