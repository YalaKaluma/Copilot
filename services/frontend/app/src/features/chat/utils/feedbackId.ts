/**
 * Message-like shape used for resolving the assistant message ID for feedback.
 * Matches the Message type from useLLM for feedback purposes.
 */
export interface MessageForFeedback {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  assistantMessageId?: string;
}

/** UUID v4 format (lowercase hex with dashes). */
export const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Returns the assistant message ID suitable for the feedback API, or null if
 * the message is not an assistant message with content or the ID is not a valid UUID.
 * Prefers assistantMessageId (server-assigned) when present, otherwise message.id.
 */
export function getAssistantMessageId(message: MessageForFeedback): string | null {
  if (message.role !== 'assistant' || !message.content) return null;
  const id = message.assistantMessageId ?? message.id;
  return UUID_REGEX.test(id) ? id : null;
}
