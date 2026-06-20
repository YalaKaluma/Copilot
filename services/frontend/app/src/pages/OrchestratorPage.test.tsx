import { act, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, afterEach, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { OrchestratorPage } from './OrchestratorPage';
import type { UseChatHistoryReturn } from '../features/chat/hooks/useChatHistory';
import type { Message } from '../features/chat/hooks/useLLM';

const orchestratorHookMocks = vi.hoisted(() => ({
  useOrchestratorChat: vi.fn(),
  markSessionDeleted: vi.fn(),
}));

const apiClientMocks = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('@clerk/clerk-react', () => ({
  useAuth: () => ({ isLoaded: true, isSignedIn: true }),
}));

vi.mock('../shared/lib/config', () => ({
  config: { isProd: true },
}));

vi.mock('../shared/lib/api-client', () => ({
  apiClient: {
    get: apiClientMocks.get,
  },
}));

vi.mock('../features/projects', () => ({
  projectService: {
    getProject: vi.fn().mockResolvedValue({ id: 'p1', name: 'Project' }),
  },
}));

vi.mock('../features/chat/hooks/useTemplates', () => ({
  useTemplates: () => ({
    templates: [],
    activeTemplate: null,
    fetchTemplates: vi.fn().mockResolvedValue(undefined),
    selectTemplate: vi.fn().mockResolvedValue(undefined),
    clearActiveTemplate: vi.fn(),
    createTemplate: vi.fn().mockResolvedValue({
      id: 'tpl-1',
      name: 'Template',
      content: 'Body',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }),
  }),
}));

vi.mock('../features/chat/hooks/useOrchestratorChat', () => ({
  useOrchestratorChat: orchestratorHookMocks.useOrchestratorChat,
  markSessionDeleted: orchestratorHookMocks.markSessionDeleted,
}));

vi.mock('../shared/components/layout/ChatTopBar', () => ({
  ChatTopBar: () => <div data-testid="chat-top-bar" />,
}));

vi.mock('../features/chat/components/OrchestratorChatInterface', () => ({
  OrchestratorChatInterface: () => <div data-testid="orchestrator-chat-interface" />,
}));

vi.mock('../features/chat/components/ExecutionPlanPanel', () => ({
  ExecutionPlanPanel: () => <div data-testid="execution-plan-panel" />,
}));

vi.mock('../features/chat/components/ReasoningPanel', () => ({
  ReasoningPanel: () => <div data-testid="reasoning-panel" />,
}));

vi.mock('../features/chat/components/ReportPanel', () => ({
  ReportPanel: () => <div data-testid="report-panel" />,
}));

vi.mock('../features/chat/components/ChartsPanel', () => ({
  ChartsPanel: () => <div data-testid="charts-panel" />,
}));

vi.mock('../shared/components/layout/ChatLeftSidebar', () => ({
  ChatLeftSidebar: ({ conversations }: { conversations: unknown[] }) => (
    <pre data-testid="sidebar-conversations">{JSON.stringify(conversations)}</pre>
  ),
}));

const baseMessages: Message[] = [
  {
    id: 'u-1',
    role: 'user',
    content: 'question',
    timestamp: new Date(),
  },
  {
    id: 'a-1',
    role: 'assistant',
    content: 'answer',
    timestamp: new Date(),
  },
];

const baseConversationList = [
  {
    id: 'conv-active',
    sessionId: 'session-active',
    title: 'Active',
    stage: 'planning',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    messageCount: 1,
  },
  {
    id: 'conv-other',
    sessionId: 'session-other',
    title: 'Other',
    stage: 'execution',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    messageCount: 8,
  },
];

const renderPage = (chatHistory: UseChatHistoryReturn) =>
  render(
    <MemoryRouter>
      <OrchestratorPage chatHistory={chatHistory} sessionId="session-active" hasSessionInUrl />
    </MemoryRouter>
  );

describe('OrchestratorPage chat ownership model', () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it('overlays active chat entry with local UI stage while keeping other chats from history', async () => {
    apiClientMocks.get.mockResolvedValue({ connected: true });
    orchestratorHookMocks.useOrchestratorChat.mockReturnValue({
      messages: [...baseMessages, { ...baseMessages[0], id: 'u-2' }],
      isLoading: false,
      isStreaming: false,
      isGeneratingReport: false,
      currentStage: 'done',
      isWorkflowComplete: true,
      plan: null,
      executionLog: [],
      charts: [],
      sendMessage: vi.fn().mockResolvedValue({ ok: true, persisted: true, sessionId: 'session-active' }),
      clearMessages: vi.fn(),
      clearSession: vi.fn().mockResolvedValue(undefined),
      sessionId: 'session-active',
      conversationId: 'conv-active',
      updateMessageFeedback: vi.fn(),
      markActionSelected: vi.fn(),
    });

    const chatHistory: UseChatHistoryReturn = {
      conversations: baseConversationList,
      isLoading: false,
      fetchHistory: vi.fn().mockResolvedValue(undefined),
      deleteChat: vi.fn().mockResolvedValue(undefined),
      selectChat: vi.fn().mockResolvedValue(null),
    };

    renderPage(chatHistory);

    await waitFor(() => {
      const rendered = JSON.parse(screen.getByTestId('sidebar-conversations').textContent ?? '[]') as Array<{
        sessionId: string;
        stage: string | null;
        messageCount: number;
      }>;
      const active = rendered.find((conv) => conv.sessionId === 'session-active');
      const other = rendered.find((conv) => conv.sessionId === 'session-other');

      expect(active?.stage).toBe('done');
      expect(active?.messageCount).toBe(3);
      expect(other?.stage).toBe('execution');
      expect(other?.messageCount).toBe(8);
    });
  });

  it('polls history list on an interval for non-active chats', async () => {
    vi.useFakeTimers();
    apiClientMocks.get.mockReturnValue(new Promise(() => {}));
    orchestratorHookMocks.useOrchestratorChat.mockReturnValue({
      messages: baseMessages,
      isLoading: false,
      isStreaming: false,
      isGeneratingReport: false,
      currentStage: 'planning',
      isWorkflowComplete: false,
      plan: null,
      executionLog: [],
      charts: [],
      sendMessage: vi.fn().mockResolvedValue({ ok: true, persisted: true, sessionId: 'session-active' }),
      clearMessages: vi.fn(),
      clearSession: vi.fn().mockResolvedValue(undefined),
      sessionId: 'session-active',
      conversationId: 'conv-active',
      updateMessageFeedback: vi.fn(),
      markActionSelected: vi.fn(),
    });

    const fetchHistory = vi.fn().mockResolvedValue(undefined);
    const chatHistory: UseChatHistoryReturn = {
      conversations: baseConversationList,
      isLoading: false,
      fetchHistory,
      deleteChat: vi.fn().mockResolvedValue(undefined),
      selectChat: vi.fn().mockResolvedValue(null),
    };

    renderPage(chatHistory);

    expect(fetchHistory).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(fetchHistory).toHaveBeenCalledTimes(1);

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(fetchHistory).toHaveBeenCalledTimes(2);

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(fetchHistory).toHaveBeenCalledTimes(3);
  });
});
