import { describe, it, expect } from 'vitest';
import { getAssistantMessageId, UUID_REGEX } from './feedbackId';
import type { MessageForFeedback } from './feedbackId';

const validUuid = 'a1b2c3d4-e5f6-4789-a012-3456789abcde';
const validUuidUpper = 'A1B2C3D4-E5F6-4789-A012-3456789ABCDE';

describe('UUID_REGEX', () => {
  it('accepts lowercase UUID v4 format', () => {
    expect(UUID_REGEX.test(validUuid)).toBe(true);
  });

  it('accepts uppercase UUID', () => {
    expect(UUID_REGEX.test(validUuidUpper)).toBe(true);
  });

  it('rejects non-hex characters', () => {
    expect(UUID_REGEX.test('g1b2c3d4-e5f6-4789-a012-3456789abcde')).toBe(false);
  });

  it('rejects wrong segment lengths', () => {
    expect(UUID_REGEX.test('a1b2c3d4-e5f6-4789-a012-3456789abc')).toBe(false);
    expect(UUID_REGEX.test('a1b2c3d4e5f6-4789-a012-3456789abcde')).toBe(false);
  });

  it('rejects empty string', () => {
    expect(UUID_REGEX.test('')).toBe(false);
  });
});

describe('getAssistantMessageId', () => {
  it('returns id when role is assistant, has content, and id is valid UUID', () => {
    const message: MessageForFeedback = {
      id: validUuid,
      role: 'assistant',
      content: 'Hello',
    };
    expect(getAssistantMessageId(message)).toBe(validUuid);
  });

  it('prefers assistantMessageId over id when both present', () => {
    const serverId = 'b2c3d4e5-f6a7-8901-bcde-f12345678901';
    const message: MessageForFeedback = {
      id: validUuid,
      role: 'assistant',
      content: 'Hello',
      assistantMessageId: serverId,
    };
    expect(getAssistantMessageId(message)).toBe(serverId);
  });

  it('returns null for user role', () => {
    const message: MessageForFeedback = {
      id: validUuid,
      role: 'user',
      content: 'Hello',
    };
    expect(getAssistantMessageId(message)).toBe(null);
  });

  it('returns null for system role', () => {
    const message: MessageForFeedback = {
      id: validUuid,
      role: 'system',
      content: 'Hello',
    };
    expect(getAssistantMessageId(message)).toBe(null);
  });

  it('returns null when content is empty string', () => {
    const message: MessageForFeedback = {
      id: validUuid,
      role: 'assistant',
      content: '',
    };
    expect(getAssistantMessageId(message)).toBe(null);
  });

  it('returns null when id is not a valid UUID', () => {
    const message: MessageForFeedback = {
      id: 'not-a-uuid',
      role: 'assistant',
      content: 'Hello',
    };
    expect(getAssistantMessageId(message)).toBe(null);
  });

  it('returns null when assistantMessageId is set but not a valid UUID', () => {
    const message: MessageForFeedback = {
      id: validUuid,
      role: 'assistant',
      content: 'Hello',
      assistantMessageId: 'client-id-123',
    };
    expect(getAssistantMessageId(message)).toBe(null);
  });

  it('is consistent: same message always returns same result', () => {
    const message: MessageForFeedback = {
      id: validUuid,
      role: 'assistant',
      content: 'Same content',
    };
    expect(getAssistantMessageId(message)).toBe(getAssistantMessageId(message));
    expect(getAssistantMessageId(message)).toBe(validUuid);
  });
});
