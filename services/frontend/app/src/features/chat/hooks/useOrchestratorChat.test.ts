import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useOrchestratorChat } from './useOrchestratorChat';
import type { ConversationDetail } from '../types/chatHistory.types';

const apiClientMocks = vi.hoisted(() => ({
  stream: vi.fn(),
}));

const chatHistoryServiceMocks = vi.hoisted(() => ({
  saveConversation: vi.fn().mockResolvedValue({
    id: 'conv-1',
    sessionId: 'session-1',
    title: null,
    stage: 'planning',
  }),
  generateTitle: vi.fn().mockResolvedValue({ id: 'conv-1', title: 'Title' }),
  generateReport: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('@clerk/clerk-react', () => ({
  useAuth: () => ({
    getToken: vi.fn().mockResolvedValue('token'),
  }),
}));

vi.mock('../services/chatHistoryService', () => ({
  chatHistoryService: {
    saveConversation: chatHistoryServiceMocks.saveConversation,
    generateTitle: chatHistoryServiceMocks.generateTitle,
    generateReport: chatHistoryServiceMocks.generateReport,
  },
}));

vi.mock('../../../shared/lib/api-client', () => ({
  __esModule: true,
  default: {
    stream: apiClientMocks.stream,
  },
}));

const buildSseResponse = (events: Array<Record<string, unknown>>) => {
  const payload = events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('');
  return new Response(payload, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  });
};

const buildConversation = (
  stage: string | null,
  userMessages: number,
  sessionId = 'session-1'
): ConversationDetail => {
  const messages: ConversationDetail['messages'] = [];
  for (let i = 0; i < userMessages; i += 1) {
    messages.push({
      id: `u-${i}`,
      role: 'user',
      content: `user-${i}`,
      messageMetadata: null,
      createdAt: new Date().toISOString(),
      feedback: null,
    });
  }
  messages.push({
    id: 'a-1',
    role: 'assistant',
    content: 'final answer',
    messageMetadata: null,
    createdAt: new Date().toISOString(),
    feedback: null,
  });

  return {
    id: 'conv-1',
    sessionId,
    title: 'Conversation',
    stage,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    messageCount: messages.length,
    messages,
    planData: null,
    executionLog: [],
    charts: [],
    report: null,
  };
};

describe('useOrchestratorChat hydration stage merging', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatHistoryServiceMocks.saveConversation.mockResolvedValue({
      id: 'conv-1',
      sessionId: 'session-1',
      title: null,
      stage: 'planning',
    });
    chatHistoryServiceMocks.generateTitle.mockResolvedValue({ id: 'conv-1', title: 'Title' });
    chatHistoryServiceMocks.generateReport.mockResolvedValue(undefined);
  });

  it('ignores mismatched stream session_id so old chat id cannot override current chat id', async () => {
    chatHistoryServiceMocks.saveConversation.mockResolvedValue({
      id: 'conv-new',
      sessionId: 'session-new',
      title: null,
      stage: 'done',
    });
    apiClientMocks.stream.mockResolvedValueOnce(
      buildSseResponse([
        { type: 'thinking', content: 'thinking', session_id: 'session-old' },
        { type: 'done', final_answer: 'final', session_id: 'session-new' },
      ])
    );

    const { result } = renderHook(() => useOrchestratorChat('session-new', undefined, {}));
    let sendResult: Awaited<ReturnType<typeof result.current.sendMessage>> | null = null;
    await act(async () => {
      sendResult = await result.current.sendMessage('hello');
    });

    expect(sendResult?.ok).toBe(true);
    expect(sendResult?.sessionId).toBe('session-new');
    expect(result.current.sessionId).toBe('session-new');
    expect(result.current.messages[result.current.messages.length - 1]?.content).toContain('final');
    expect(chatHistoryServiceMocks.saveConversation).not.toHaveBeenCalledWith(
      expect.objectContaining({ sessionId: 'session-old' })
    );
  });

  it('stops stream processing after done so trailing thinking events do not keep generation alive', async () => {
    chatHistoryServiceMocks.saveConversation.mockResolvedValue({
      id: 'conv-1',
      sessionId: 'session-1',
      title: null,
      stage: 'done',
    });
    apiClientMocks.stream.mockResolvedValueOnce(
      buildSseResponse([
        { type: 'done', final_answer: 'Final answer', session_id: 'session-1' },
        { type: 'thinking', content: 'should-not-appear', session_id: 'session-1' },
      ])
    );

    const { result } = renderHook(() => useOrchestratorChat('session-1', undefined, {}));
    await act(async () => {
      await result.current.sendMessage('hello');
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.currentStage).toBe('done');
    });
    const assistant = [...result.current.messages].reverse().find((m) => m.role === 'assistant');
    expect(assistant?.statusLines ?? []).not.toContain('Reasoning: should-not-appear');
  });

  it('does not persist waiting_for_info with mismatched stream session id', async () => {
    chatHistoryServiceMocks.saveConversation.mockResolvedValue({
      id: 'conv-new',
      sessionId: 'session-new',
      title: null,
      stage: 'waiting_for_info',
    });
    apiClientMocks.stream.mockResolvedValueOnce(
      buildSseResponse([
        { type: 'stage_start', stage: 'planning', session_id: 'session-new' },
        { type: 'waiting_for_info', content: 'need more data', session_id: 'session-old' },
      ])
    );

    const { result } = renderHook(() => useOrchestratorChat('session-new', undefined, {}));
    await act(async () => {
      await result.current.sendMessage('hello');
    });

    expect(chatHistoryServiceMocks.saveConversation).not.toHaveBeenCalledWith(
      expect.objectContaining({ sessionId: 'session-old' })
    );
    expect(result.current.sessionId).toBe('session-new');
  });

  it('finalizes only when done event is received', async () => {
    chatHistoryServiceMocks.saveConversation.mockResolvedValue({
      id: 'conv-1',
      sessionId: 'session-1',
      title: null,
      stage: 'done',
    });
    apiClientMocks.stream.mockResolvedValueOnce(
      buildSseResponse([
        { type: 'content', stage: 'execution', content: 'Final answer text', session_id: 'session-1' },
        { type: 'done', stage: 'done', content: 'Orchestrator session completed', session_id: 'session-1', message_id: 'msg-1' },
      ])
    );

    const { result } = renderHook(() => useOrchestratorChat('session-1', undefined, {}));
    await act(async () => {
      await result.current.sendMessage('hello');
    });

    await waitFor(() => {
      expect(result.current.currentStage).toBe('done');
      expect(result.current.isWorkflowComplete).toBe(true);
      expect(result.current.isLoading).toBe(false);
    });
    const assistant = [...result.current.messages].reverse().find((m) => m.role === 'assistant');
    expect(assistant?.content).toContain('Final answer text');
  });

  it('does not finalize when only stage_complete is received (no done event)', async () => {
    chatHistoryServiceMocks.saveConversation.mockResolvedValue({
      id: 'conv-1',
      sessionId: 'session-1',
      title: null,
      stage: 'done',
    });
    apiClientMocks.stream.mockResolvedValueOnce(
      buildSseResponse([
        { type: 'content', stage: 'execution', content: 'Final answer text', session_id: 'session-1' },
        { type: 'stage_complete', stage: 'done', content: 'Workflow complete', session_id: 'session-1' },
      ])
    );

    const { result } = renderHook(() => useOrchestratorChat('session-1', undefined, {}));
    await act(async () => {
      await result.current.sendMessage('hello');
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.currentStage).toBe('done');
    expect(result.current.isWorkflowComplete).toBe(false);
    expect(chatHistoryServiceMocks.generateReport).not.toHaveBeenCalled();
  });

  it('does not regress active stage for same turn when snapshot is stale', async () => {
    const doneConversation = buildConversation('done', 1);
    const stalePlanningSnapshot = buildConversation('planning', 1);

    const { result, rerender } = renderHook(
      ({ initialConversation }) =>
        useOrchestratorChat('session-1', initialConversation, {}),
      { initialProps: { initialConversation: doneConversation } }
    );

    await waitFor(() => {
      expect(result.current.currentStage).toBe('done');
      expect(result.current.isWorkflowComplete).toBe(true);
    });

    rerender({ initialConversation: stalePlanningSnapshot });

    await waitFor(() => {
      expect(result.current.currentStage).toBe('done');
      expect(result.current.isWorkflowComplete).toBe(true);
    });
  });

  it('accepts lower stage when snapshot belongs to a newer user turn', async () => {
    const doneConversation = buildConversation('done', 1);
    const nextTurnPlanningSnapshot = buildConversation('planning', 2);

    const { result, rerender } = renderHook(
      ({ initialConversation }) =>
        useOrchestratorChat('session-1', initialConversation, {}),
      { initialProps: { initialConversation: doneConversation } }
    );

    await waitFor(() => {
      expect(result.current.currentStage).toBe('done');
    });

    rerender({ initialConversation: nextTurnPlanningSnapshot });

    await waitFor(() => {
      expect(result.current.currentStage).toBe('planning');
      expect(result.current.isWorkflowComplete).toBe(false);
    });
  });
});
