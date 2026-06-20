import { useState, useCallback, useRef, useEffect } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { toast } from 'sonner';
import apiClient from '../../../shared/lib/api-client';
import { Message } from './useLLM';
import type { FeedbackCategory } from '../services/feedbackService';
import { getAssistantMessageId } from '../utils/feedbackId';
import { chatHistoryService } from '../services/chatHistoryService';
import type { ConversationDetail } from '../types/chatHistory.types';
import type { ChartItem, ChartSpec } from '../types/chart.types';
import { createAsyncSerialTaskQueue } from '../utils/asyncQueue';

// Module-level map of deleted session IDs → deletion timestamp.
// Background streams that outlive their component mount check this before
// persisting so a deleted chat doesn't get re-created by a stray periodic save.
// Entries auto-expire after DELETED_SESSION_TTL_MS to prevent unbounded growth.
const DELETED_SESSION_TTL_MS = 2 * 60 * 1000; // 2 minutes
const deletedSessionIds = new Map<string, number>();

/** Mark a session as deleted so background streams stop persisting it. */
export function markSessionDeleted(sessionId: string): void {
  deletedSessionIds.set(sessionId, Date.now());
  // Lazy cleanup: prune expired entries whenever we add a new one
  const now = Date.now();
  for (const [id, ts] of deletedSessionIds) {
    if (now - ts > DELETED_SESSION_TTL_MS) deletedSessionIds.delete(id);
  }
}

interface OrchestratorEvent {
  type: 'stage_change' | 'stage_start' | 'stage_complete' | 'content' | 'plan' | 'plan_created' | 'request_info' | 'waiting_for_info' | 'handoff' | 'tool_call' | 'tool_result' | 'thinking' | 'progress' | 'done' | 'error' | 'chart';
  stage?: string;
  content?: string;
  plan?: Record<string, unknown>;
  chart?: ChartSpec;
  request?: string;
  actions?: string[];
  allow_other?: boolean;
  error?: string;
  transient?: boolean;
  completed?: boolean;
  final_answer?: string;
  step_number?: number;
  total_steps?: number;
  tool_name?: string;
  tool_args?: Record<string, unknown>;
  tool_result?: unknown;
  metadata?: Record<string, unknown>;
  session_id?: string;
  /** Backend-generated message id (Phase 2); use for save and feedback */
  message_id?: string;
  choices?: Array<{ delta?: { content?: string } }>;
}

export interface ExecutionLogEntry {
  id: string;
  agent: string;
  toolName: string;
  status: 'running' | 'completed' | 'error';
  args?: Record<string, unknown>;
  result?: unknown;
  content?: string;
  timestamp: Date;
  stepNumber?: number;
  totalSteps?: number;
}

interface UseOrchestratorChatReturn {
  messages: Message[];
  isLoading: boolean;
  isStreaming: boolean;
  isGeneratingReport: boolean;
  currentStage: string | null;
  isWorkflowComplete: boolean;
  plan: Record<string, unknown> | null;
  executionLog: ExecutionLogEntry[];
  charts: ChartItem[];
  sendMessage: (
    content: string,
    templateContext?: { name: string; content: string } | null
  ) => Promise<SendMessageResult>;
  clearMessages: () => void;
  clearSession: () => Promise<void>;
  sessionId: string | null;
  conversationId: string | null;
  updateMessageFeedback: (
    assistantMessageId: string,
    feedback: { category: FeedbackCategory; reason?: string } | null
  ) => void;
  markActionSelected: (messageId: string, action: string) => void;
}

interface SendMessageResult {
  ok: boolean;
  persisted: boolean;
  sessionId: string | null;
}

interface StreamRequestError extends Error {
  status?: number;
  detail?: string;
  errorCode?: string;
}

const splitActionText = (value: string): string[] => {
  const trimmed = value.replace(/\r\n/g, '\n').trim();
  if (!trimmed) return [];
  const withBreaks = trimmed.replace(/\s+(?=\d+[.)]\s+)/g, '\n');
  return withBreaks
    .split('\n')
    .map((line) => line.replace(/^\s*(?:[-*•]\s+|\d+[.)]\s+)/, '').trim())
    .filter((line) => line.length > 0);
};

const normalizeActions = (rawActions?: string[], limit = 3): string[] | undefined => {
  if (!rawActions || rawActions.length === 0) return undefined;
  const unique = new Set<string>();
  const actions: string[] = [];
  for (const raw of rawActions) {
    const candidates = splitActionText(typeof raw === 'string' ? raw : '');
    for (const candidate of candidates) {
      if (unique.has(candidate)) continue;
      unique.add(candidate);
      actions.push(candidate);
      if (actions.length >= limit) return actions;
    }
  }
  return actions.length > 0 ? actions : undefined;
};

const stageRank = (stage: string | null): number => {
  switch (stage) {
    case 'scoping':
      return 0;
    case 'planning':
      return 1;
    case 'execution':
      return 2;
    case 'waiting_for_info':
      return 3;
    case 'done':
      return 4;
    default:
      return -1;
  }
};

const countUserMessages = (messages: Message[]): number =>
  messages.reduce((count, message) => (message.role === 'user' ? count + 1 : count), 0);

const restoreMessages = (conversation: ConversationDetail): Message[] =>
  conversation.messages.map((m, i) => ({
    id: m.id || `restored-${i}`,
    role: m.role as Message['role'],
    content: m.content,
    timestamp: new Date(m.createdAt),
    statusLines: m.messageMetadata?.statusLines as string[] | undefined,
    actions: m.messageMetadata?.actions as string[] | undefined,
    allowOther: m.messageMetadata?.allowOther as boolean | undefined,
    selectedAction: m.messageMetadata?.selectedAction as string | undefined,
    feedback: m.feedback ?? undefined,
  }));

export interface UseOrchestratorChatOptions {
  /** Called with session id before sending when we had none (new chat). Use to update URL before the request. */
  onSessionIdBeforeSend?: (sessionId: string) => void;
  /** Optional copilot version id (e.g. v1); when provided, orchestrator uses this instead of backend default. */
  skaiVersion?: string | null;
  /** Optional project id to scope the conversation to a project when saving. */
  projectId?: string | null;
  /** Called after a conversation title is generated so the parent can refresh sidebar history. */
  onTitleGenerated?: () => void;
  /** User-selected filter options (camelCase keys) to send with the chat request. Applied only to new queries. */
  filterOptions?: Record<string, string[]> | null;
}

export function useOrchestratorChat(
  sessionId?: string,
  initialConversation?: ConversationDetail,
  options?: UseOrchestratorChatOptions
): UseOrchestratorChatReturn {
  const { onSessionIdBeforeSend, skaiVersion, projectId, onTitleGenerated, filterOptions } = options ?? {};
  const { getToken } = useAuth();
  const [messages, setMessages] = useState<Message[]>(() => {
    if (!initialConversation) return [];
    return restoreMessages(initialConversation);
  });
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [currentStage, setCurrentStage] = useState<string | null>(
    initialConversation?.stage || null
  );
  const [isWorkflowComplete, setIsWorkflowComplete] = useState(
    initialConversation?.stage === 'done'
  );
  const [plan, setPlan] = useState<Record<string, unknown> | null>(
    initialConversation?.planData || null
  );
  const [executionLog, setExecutionLog] = useState<ExecutionLogEntry[]>(
    initialConversation?.executionLog || []
  );
  const [charts, setCharts] = useState<ChartItem[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(
    initialConversation?.id || null
  );
  const [runtimeSessionId, setRuntimeSessionId] = useState<string | null>(
    initialConversation?.sessionId || sessionId || null
  );
  const messagesRef = useRef<Message[]>(messages);
  const planRef = useRef<Record<string, unknown> | null>(plan);
  const executionLogRef = useRef<ExecutionLogEntry[]>(executionLog);
  const chartsRef = useRef<ChartItem[]>(charts);
  const currentStageRef = useRef<string | null>(currentStage);
  const sessionIdRef = useRef<string | null>(initialConversation?.sessionId || sessionId || null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const activeRequestIdRef = useRef(0);
  const persistQueueRef = useRef(createAsyncSerialTaskQueue());
  // Increments whenever the active chat context is reset/switched.
  // Persist tasks capture this value so stale queued saves can't
  // overwrite session state after "new chat" or chat navigation.
  const chatContextVersionRef = useRef(0);
  const sessionsSeenDoneRef = useRef<Set<string>>(new Set());
  /** Stage we last successfully persisted; used to throttle interval and avoid duplicate stage persists. */
  const lastPersistedStageRef = useRef<string | null>(null);

  // Keep currentStageRef in sync with state for use in callbacks
  useEffect(() => {
    currentStageRef.current = currentStage;
  }, [currentStage]);

  const cancelActiveStream = useCallback(() => {
    activeRequestIdRef.current += 1;
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsLoading(false);
    setIsStreaming(false);
  }, []);

  // Rehydrate local state when async conversation hydration completes.
  const prevConversationRef = useRef<ConversationDetail | undefined>(initialConversation);
  useEffect(() => {
    if (initialConversation) {
      // If the user is actively streaming in this mount (e.g. they came back
      // and started a new message), don't clobber state with poll data.
      const isSameConversation =
        prevConversationRef.current?.sessionId === initialConversation.sessionId;
      const hasActiveStream =
        abortControllerRef.current !== null && !abortControllerRef.current.signal.aborted;
      const isStreamingThisSession =
        hasActiveStream &&
        initialConversation.sessionId != null &&
        initialConversation.sessionId === sessionIdRef.current;
      if (isStreamingThisSession || (isSameConversation && hasActiveStream)) {
        // Don't overwrite live stream state with (stale) polled DB data.
        prevConversationRef.current = initialConversation;
        return;
      }

      if (!isSameConversation) {
        chatContextVersionRef.current += 1;
        cancelActiveStream();
      }
      const restoredMessages = restoreMessages(initialConversation);
      const restoredPlan = initialConversation.planData || null;
      const restoredExecutionLog = initialConversation.executionLog || [];
      const rawCharts = initialConversation.charts ?? [];
      const restoredCharts: ChartItem[] = rawCharts.map((c, i) => ({
        id: c.id ?? `restored-${i}-${Date.now()}`,
        title: c.title ?? '',
        chartType: c.chartType ?? 'bar',
        data: c.data ?? [],
      }));
      const restoredSessionId = initialConversation.sessionId || sessionId || null;
      let restoredStage = initialConversation.stage || null;
      const localStage = currentStageRef.current;
      const localMessages = messagesRef.current;
      const hasNewerUserTurn = countUserMessages(restoredMessages) > countUserMessages(localMessages);
      // Never regress a session we've seen as "done" (e.g. stale fetch when switching back), unless it's a newer user turn.
      if (
        restoredSessionId &&
        !hasNewerUserTurn &&
        restoredStage !== 'done' &&
        sessionsSeenDoneRef.current.has(restoredSessionId)
      ) {
        restoredStage = 'done';
      }
      // Prevent polling snapshots from regressing stage for the same turn.
      // This avoids flicker/backtracking when stream state is ahead of persisted state.
      const shouldPreserveLocalStage =
        isSameConversation &&
        !hasNewerUserTurn &&
        stageRank(localStage) > stageRank(restoredStage);
      if (shouldPreserveLocalStage) {
        prevConversationRef.current = initialConversation;
        return;
      }

      messagesRef.current = restoredMessages;
      planRef.current = restoredPlan;
      executionLogRef.current = restoredExecutionLog;
      chartsRef.current = restoredCharts;
      sessionIdRef.current = restoredSessionId;

      setMessages(restoredMessages);
      setPlan(restoredPlan);
      setExecutionLog(restoredExecutionLog);
      setCharts(restoredCharts);
      setConversationId(initialConversation.id || null);
      setRuntimeSessionId(restoredSessionId);
      setCurrentStage(restoredStage);
      setIsWorkflowComplete(restoredStage === 'done');
      if (restoredStage === 'done' && restoredSessionId) {
        sessionsSeenDoneRef.current.add(restoredSessionId);
      }
      // Show loading indicator only when the AI is actively processing.
      // Don't show loading for 'done' or 'waiting_for_info' — in both
      // cases the AI is idle and the user should be able to interact.
      const isInFlight =
        restoredStage !== null &&
        restoredStage !== 'done' &&
        restoredStage !== 'waiting_for_info';
      setIsLoading(isInFlight);
      setIsGeneratingReport(false);
      prevConversationRef.current = initialConversation;
      return;
    }

    // Reset state when initialConversation transitions from a loaded
    // conversation to undefined (e.g. switching between chats while the
    // new conversation is being fetched).  Without this, the previous
    // conversation's messages would persist until the fetch completes.
    if (prevConversationRef.current) {
      chatContextVersionRef.current += 1;
      cancelActiveStream();
      messagesRef.current = [];
      planRef.current = null;
      executionLogRef.current = [];
      chartsRef.current = [];
      sessionIdRef.current = sessionId || null;

      setMessages([]);
      setPlan(null);
      setExecutionLog([]);
      setCharts([]);
      setConversationId(null);
      setRuntimeSessionId(sessionId || null);
      setCurrentStage(null);
      setIsWorkflowComplete(false);
      setIsGeneratingReport(false);
      prevConversationRef.current = undefined;
      return;
    }

    if (sessionId && sessionId !== sessionIdRef.current) {
      chatContextVersionRef.current += 1;
      cancelActiveStream();
      sessionIdRef.current = sessionId;
      setRuntimeSessionId(sessionId);
    }
  }, [initialConversation, sessionId, cancelActiveStream]);

  // On unmount: persist partial state but do NOT abort the stream.
  // The stream continues running in the background so the AI finishes
  // processing and persists the final result on completion (done event).
  // React 18+ silently ignores state updates on unmounted components,
  // while refs in the closure stay valid for the persist call.
  // Use sessionsSeenDoneRef so we never overwrite a completed conversation with scoping/executing.
  useEffect(() => {
    const sessionsSeenDone = sessionsSeenDoneRef.current;
    const persistConversation = persistConversationRef.current;

    return () => {
      if (messagesRef.current.length > 0 && sessionIdRef.current) {
        let stage = currentStageRef.current || 'scoping';
        const sid = sessionIdRef.current;
        if (stage !== 'done' && sid && sessionsSeenDone.has(sid)) {
          stage = 'done';
        }
        void persistConversation(stage, false).catch(() => {});
      }
    };
  }, []);

  const resolveAgent = useCallback((event: OrchestratorEvent) => {
    const agent = event.metadata && typeof event.metadata.agent === 'string'
      ? event.metadata.agent
      : null;
    return agent || 'orchestrator';
  }, []);

  const recordToolCall = useCallback((event: OrchestratorEvent) => {
    const agent = resolveAgent(event);
    const toolName = event.tool_name || 'unknown_tool';
    const newEntry: ExecutionLogEntry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      agent,
      toolName,
      status: 'running',
      args: event.tool_args,
      content: event.content,
      timestamp: new Date(),
      stepNumber: event.step_number,
      totalSteps: event.total_steps,
    };
    setExecutionLog((prev) => {
      const next = [...prev, newEntry];
      executionLogRef.current = next;
      return next;
    });
  }, [resolveAgent]);

  const recordToolResult = useCallback((event: OrchestratorEvent) => {
    const agent = resolveAgent(event);
    const toolName = event.tool_name || 'unknown_tool';
    setExecutionLog((prev) => {
      const next = [...prev];
      const updateEntry = (index: number, overrides: Partial<ExecutionLogEntry> = {}) => {
        next[index] = {
          ...next[index],
          status: 'completed',
          result: event.tool_result,
          content: event.content || next[index].content,
          stepNumber: event.step_number ?? next[index].stepNumber,
          totalSteps: event.total_steps ?? next[index].totalSteps,
          ...overrides,
        };
      };

      let matched = false;
      for (let i = next.length - 1; i >= 0; i -= 1) {
        if (next[i].agent === agent && next[i].toolName === toolName && next[i].status === 'running') {
          updateEntry(i);
          matched = true;
          break;
        }
      }

      if (event.tool_name === 'hand_back' && agent !== 'orchestrator') {
        const handoffTool = `${agent}_handoff`;
        for (let i = next.length - 1; i >= 0; i -= 1) {
          if (next[i].agent === 'orchestrator' && next[i].toolName === handoffTool && next[i].status === 'running') {
            updateEntry(i, { content: `${handoffTool} completed` });
            matched = true;
            break;
          }
        }
      }

      if (matched) {
        executionLogRef.current = next;
        return next;
      }
      next.push({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        agent,
        toolName,
        status: 'completed',
        args: event.tool_args,
        result: event.tool_result,
        content: event.content,
        timestamp: new Date(),
        stepNumber: event.step_number,
        totalSteps: event.total_steps,
      });
      executionLogRef.current = next;
      return next;
    });
  }, [resolveAgent]);

  const syncMessages = useCallback((updater: (prev: Message[]) => Message[]) => {
    const next = updater(messagesRef.current);
    messagesRef.current = next;
    setMessages(next);
    return next;
  }, []);

  const persistConversation = useCallback(
    async (
      stage: string | null,
      generateTitle = false,
      sessionIdOverride?: string
    ): Promise<{ ok: boolean; sessionId: string | null }> => {
      const contextVersionAtEnqueue = chatContextVersionRef.current;
      const isPriority = stage === 'done';
      const queue = persistQueueRef.current;
      const run = (isPriority ? queue.enqueuePriority : queue.enqueue).bind(queue);
      return run(async () => {
        if (contextVersionAtEnqueue !== chatContextVersionRef.current) {
          return { ok: false, sessionId: sessionIdRef.current };
        }
        // Skip persist if this session was deleted by the user.
        const sid = sessionIdOverride ?? sessionIdRef.current;
        if (sid && deletedSessionIds.has(sid)) {
          return { ok: false, sessionId: sid };
        }

        const currentMessages = messagesRef.current;
        try {
          const targetSessionId = sessionIdOverride ?? sessionIdRef.current;
          const resp = await chatHistoryService.saveConversation({
            sessionId: targetSessionId,
            stage,
            planData: planRef.current,
            executionLog: executionLogRef.current,
            charts: chartsRef.current,
            messages: currentMessages.map((m) => {
              const metadata: Record<string, unknown> = {};
              if (m.statusLines) metadata.statusLines = m.statusLines;
              if (m.actions) metadata.actions = m.actions;
              if (m.allowOther != null) metadata.allowOther = m.allowOther;
              if (m.selectedAction) metadata.selectedAction = m.selectedAction;
              return {
                id: m.id,
                role: m.role,
                content: m.content,
                metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
              };
            }),
            projectId: projectId ?? undefined,
          });
          if (contextVersionAtEnqueue !== chatContextVersionRef.current) {
            return { ok: false, sessionId: sessionIdRef.current };
          }
          lastPersistedStageRef.current = stage;
          sessionIdRef.current = resp.sessionId;
          setRuntimeSessionId(resp.sessionId);
          setConversationId(resp.id);
          if (generateTitle) {
            chatHistoryService.generateTitle(resp.id)
              .then(() => onTitleGenerated?.())
              .catch((err) => {
                console.warn('Failed to generate conversation title:', err);
              });
          }
          return {
            ok: true,
            sessionId: resp.sessionId,
          };
        } catch (err) {
          console.warn('Failed to save conversation:', err);
          return { ok: false, sessionId: sessionIdRef.current };
        }
      });
    },
    [projectId, onTitleGenerated]
  );

  // Ref so unmount cleanup can call the latest persistConversation without stale closures
  const persistConversationRef = useRef(persistConversation);
  useEffect(() => {
    persistConversationRef.current = persistConversation;
  }, [persistConversation]);

  const sendMessage = useCallback(
    async (content: string, templateContext?: { name: string; content: string } | null) => {
      const trimmed = content.trim();
      if (!trimmed) return { ok: false, persisted: false, sessionId: sessionIdRef.current };

      // Ensure we have a session id before sending (new chat). Generate and notify so URL can be updated before request.
      if (sessionIdRef.current == null) {
        const newId = crypto.randomUUID();
        sessionIdRef.current = newId;
        setRuntimeSessionId(newId);
        onSessionIdBeforeSend?.(newId);
      }

      const requestId = activeRequestIdRef.current + 1;
      activeRequestIdRef.current = requestId;
      abortControllerRef.current?.abort();
      const requestController = new AbortController();
      abortControllerRef.current = requestController;
      const isCurrentRequest = () =>
        activeRequestIdRef.current === requestId &&
        abortControllerRef.current === requestController &&
        !requestController.signal.aborted;

      let assistantMessageId: string | null = null;
      let assistantMessageRef: Message | null = null;
      let conversationPersisted = false;
      let persistedSessionId: string | null = sessionIdRef.current;
      let finalizedCompletion = false;
      let expectedStreamSessionId: string | null = sessionIdRef.current;
      const resolveTrustedSessionId = (incomingSessionId?: string): string | undefined => {
        if (!incomingSessionId) return undefined;
        if (!expectedStreamSessionId) {
          expectedStreamSessionId = incomingSessionId;
          return incomingSessionId;
        }
        return incomingSessionId === expectedStreamSessionId ? incomingSessionId : undefined;
      };
      const userMessage: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content: trimmed,
        timestamp: new Date(),
      };
      const finalizeCompletedWorkflow = async (doneSessionId?: string) => {
        if (finalizedCompletion) return;
        finalizedCompletion = true;
        const sid = doneSessionId ?? sessionIdRef.current ?? undefined;
        if (sid) sessionsSeenDoneRef.current.add(sid);
        currentStageRef.current = 'done';
        setCurrentStage('done');
        setIsWorkflowComplete(true);
        setIsLoading(false);
        setIsStreaming(false);

        if (!isCurrentRequest()) return;
        const saveResult = await persistConversation('done', true, sid ?? undefined);
        if (!isCurrentRequest()) return;
        conversationPersisted = saveResult.ok;
        persistedSessionId = saveResult.sessionId;

        if (saveResult.ok && persistedSessionId) {
          setIsGeneratingReport(true);
          void chatHistoryService
            .generateReport(persistedSessionId)
            .catch((err) => {
              console.warn('Failed to generate session report:', err);
              toast.error('Report could not be generated');
            })
            .finally(() => {
              setIsGeneratingReport(false);
            });
        }
      };

      syncMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      setIsStreaming(true);
      setIsGeneratingReport(false);

      // Early persist so the conversation appears in history immediately.
      // Generate a title from the user's question on the first message.
      const isFirstMessage = messagesRef.current.length === 1;
      void persistConversation(currentStageRef.current || 'scoping', isFirstMessage).catch(() => {});

      let persistInterval: number | undefined;
      try {
        const token = await getToken();
        if (!isCurrentRequest()) {
          return { ok: false, persisted: false, sessionId: sessionIdRef.current };
        }
        if (!token) {
          toast.error('Authentication required');
          syncMessages((prev) => prev.filter((msg) => msg.id !== userMessage.id));
          return { ok: false, persisted: false, sessionId: sessionIdRef.current };
        }

        const messagePayload = messagesRef.current.map((message, index, arr) => {
          let messageContent = message.content;
          // Append template context to the last message (the one just sent)
          if (templateContext && index === arr.length - 1 && message.role === 'user') {
            messageContent += `\n\n---\nTemplate: ${templateContext.name}\n${templateContext.content}`;
          }
          return { role: message.role, content: messageContent };
        });

        const assistantMessage: Message = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: '',
          timestamp: new Date(),
        };
        assistantMessageId = assistantMessage.id;
        assistantMessageRef = assistantMessage;
        syncMessages((prev) => [...prev, assistantMessage]);

        if (!isCurrentRequest()) {
          return { ok: false, persisted: false, sessionId: sessionIdRef.current };
        }

        // Backend generates assistant message id and returns it in "done" (Phase 2).
        const response = await apiClient.stream(
          '/orchestrator/chat',
          {
            messages: messagePayload,
            stream: true,
            ...(sessionIdRef.current ? { session_id: sessionIdRef.current } : {}),
            ...(skaiVersion != null && skaiVersion !== '' ? { skai_version: skaiVersion } : {}),
            ...(filterOptions != null && Object.keys(filterOptions).length > 0 ? { filter_options: filterOptions } : {}),
          },
          token,
          requestController.signal
        );
        if (!isCurrentRequest()) {
          return { ok: false, persisted: false, sessionId: sessionIdRef.current };
        }

        if (!response.ok) {
          let detail: string | undefined;
          let errorCode = response.headers.get('X-Error-Code') ?? undefined;
          try {
            const errorPayload = await response.json() as { detail?: unknown };
            if (typeof errorPayload.detail === 'string') {
              detail = errorPayload.detail;
            } else if (
              errorPayload.detail &&
              typeof errorPayload.detail === 'object' &&
              !Array.isArray(errorPayload.detail)
            ) {
              const structuredDetail = errorPayload.detail as { message?: unknown; code?: unknown };
              if (typeof structuredDetail.message === 'string') {
                detail = structuredDetail.message;
              }
              if (!errorCode && typeof structuredDetail.code === 'string') {
                errorCode = structuredDetail.code;
              }
            }
          } catch {
            // Best effort only - fallback to status code.
          }
          const requestError: StreamRequestError = new Error(
            detail ? `API error: ${response.status} - ${detail}` : `API error: ${response.status}`
          );
          requestError.status = response.status;
          requestError.detail = detail;
          requestError.errorCode = errorCode;
          throw requestError;
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (reader) {
          let buffer = '';
          let done = false;
          let shouldStopReading = false;
          const parseSseLines = async (
            lines: string[]
          ): Promise<{ aborted: false } | { aborted: true; result: { ok: false; persisted: false; sessionId: string | null } }> => {
            for (const rawLine of lines) {
              if (!isCurrentRequest()) {
                return {
                  aborted: true,
                  result: { ok: false, persisted: false, sessionId: sessionIdRef.current },
                };
              }
              const line = rawLine.trim();
              if (!line.startsWith('data:')) continue;

              const data = line.slice(5).trim();
              if (!data || data === '[DONE]') continue;

              try {
                const parsed: OrchestratorEvent = JSON.parse(data);
                if (!isCurrentRequest()) {
                  return {
                    aborted: true,
                    result: { ok: false, persisted: false, sessionId: sessionIdRef.current },
                  };
                }
                const trustedSessionId = resolveTrustedSessionId(parsed.session_id);
                if (parsed.session_id && !trustedSessionId) {
                    console.warn(
                      'Ignoring mismatched session_id from stream event',
                      expectedStreamSessionId,
                      parsed.session_id,
                      parsed.type
                    );
                } else if (trustedSessionId && trustedSessionId !== sessionIdRef.current) {
                  sessionIdRef.current = trustedSessionId;
                  persistedSessionId = trustedSessionId;
                  setRuntimeSessionId(trustedSessionId);
                }

                // Handle different event types
                switch (parsed.type) {
                  case 'stage_change':
                  case 'stage_start':
                  case 'stage_complete':
                    if (parsed.stage) {
                      const stageChanged = parsed.stage !== currentStageRef.current;
                      currentStageRef.current = parsed.stage;
                      setCurrentStage(parsed.stage);
                      if (stageChanged) {
                        const sidForPersist = trustedSessionId ?? sessionIdRef.current;
                        if (!sidForPersist || !deletedSessionIds.has(sidForPersist)) {
                          void persistConversation(parsed.stage, false, trustedSessionId).catch(() => {});
                        }
                      }
                    }
                    // Don't add stage change content to messages - it's just for tracking.
                    // Session completion is only signaled by the backend's "done" event.
                    break;

                  case 'content':
                    if (parsed.content && assistantMessageRef) {
                      if (parsed.stage === 'done') {
                        currentStageRef.current = 'done';
                        setCurrentStage('done');
                      }
                      assistantMessageRef.content += parsed.content;
                      syncMessages((prev) =>
                        prev.map((msg) =>
                          msg.id === assistantMessageRef?.id ? { ...assistantMessageRef } : msg
                        )
                      );
                    }
                    break;

                  case 'plan':
                  case 'plan_created':
                    // Plan is ready - update the plan panel immediately
                    if (parsed.plan) {
                      setPlan(parsed.plan);
                      planRef.current = parsed.plan;
                    }
                    break;

                  case 'chart': {
                    const raw = parsed.chart as Record<string, unknown> | undefined;
                    if (raw && typeof raw.title === 'string' && raw.title.trim()) {
                      const typeVal = (raw.chartType ?? raw.chart_type) as string | undefined;
                      const chartType =
                        typeVal === 'line' || typeVal === 'pie' ? typeVal : 'bar';
                      const rawData = Array.isArray(raw.data) ? raw.data : [];
                      const data: { label: string; value: number }[] = [];
                      for (const d of rawData) {
                        if (d == null || typeof d !== 'object') continue;
                        const obj = d as Record<string, unknown>;
                        const label = obj.label != null ? String(obj.label) : '';
                        const val = obj.value;
                        const num =
                          typeof val === 'number' && !Number.isNaN(val)
                            ? val
                            : typeof val === 'string'
                              ? Number.parseFloat(val)
                              : Number.NaN;
                        if (label !== '' && !Number.isNaN(num)) {
                          data.push({ label, value: num });
                        }
                      }
                      const item: ChartItem = {
                        id:
                          typeof raw.id === 'string' ? raw.id : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                        title: raw.title.trim(),
                        chartType,
                        data,
                      };
                      setCharts((prev) => {
                        const next = [...prev, item];
                        chartsRef.current = next;
                        return next;
                      });
                    }
                    break;
                  }

                  case 'request_info':
                    // Orchestrator needs more info - show the content and keep input enabled
                    if (assistantMessageRef) {
                      const rawActions = Array.isArray(parsed.actions)
                        ? parsed.actions
                        : (Array.isArray(parsed.metadata?.actions) ? parsed.metadata?.actions as string[] : undefined);
                      const actions = normalizeActions(rawActions);
                      const allowOther = typeof parsed.allow_other === 'boolean'
                        ? parsed.allow_other
                        : (typeof parsed.metadata?.allow_other === 'boolean' ? parsed.metadata?.allow_other : true);
                      // Use the formatted content from the event, or fall back to request
                      const infoContent = parsed.content ||
                        (parsed.request ? `**I need some additional information:**\n\n${parsed.request}` : '');
                      if (infoContent) {
                        assistantMessageRef.content = infoContent;
                        assistantMessageRef.actions = actions && actions.length > 0 ? actions : undefined;
                        assistantMessageRef.allowOther = allowOther;
                        syncMessages((prev) =>
                          prev.map((msg) =>
                            msg.id === assistantMessageRef?.id ? { ...assistantMessageRef } : msg
                          )
                        );
                      }
                    }
                    break;

                  case 'waiting_for_info': {
                    // Orchestrator is waiting for user input - stream is ending.
                    // Set stage to 'waiting_for_info' so the sidebar badge and
                    // progress bar reflect the paused state.
                    currentStageRef.current = 'waiting_for_info';
                    setCurrentStage('waiting_for_info');
                    // Immediately allow interaction — the AI is idle and waiting
                    // for the user to pick an action.  Without this, buttons stay
                    // disabled until the SSE connection fully closes.
                    setIsLoading(false);
                    setIsStreaming(false);
                    // Apply backend message_id so feedback uses the correct assistant_message_id
                    const backendMessageId = parsed.message_id;
                    if (
                      typeof backendMessageId === 'string' &&
                      assistantMessageRef
                    ) {
                      const previousId = assistantMessageRef.id;
                      assistantMessageRef.id = backendMessageId;
                      syncMessages((prev) =>
                        prev.map((msg) =>
                          msg.id === previousId
                            ? { ...assistantMessageRef!, id: backendMessageId }
                            : msg
                        )
                      );
                    }
                    if (!isCurrentRequest()) {
                      return {
                        aborted: true,
                        result: { ok: false, persisted: false, sessionId: sessionIdRef.current },
                      };
                    }
                    const saveResult = await persistConversation(
                      'waiting_for_info',
                      true,
                      trustedSessionId
                    );
                    if (!isCurrentRequest()) {
                      return {
                        aborted: true,
                        result: { ok: false, persisted: false, sessionId: sessionIdRef.current },
                      };
                    }
                    conversationPersisted = saveResult.ok;
                    persistedSessionId = saveResult.sessionId;
                    shouldStopReading = true;
                    break;
                  }

                  case 'progress':
                    // Progress events are status updates - show as collapsible notes
                    if (parsed.content && assistantMessageRef && !parsed.transient) {
                      if (!assistantMessageRef.statusLines) assistantMessageRef.statusLines = [];
                      assistantMessageRef.statusLines.push(parsed.content);
                      syncMessages((prev) =>
                        prev.map((msg) =>
                          msg.id === assistantMessageRef?.id ? { ...assistantMessageRef } : msg
                        )
                      );
                    }
                    break;

                  case 'tool_call': {
                    if (parsed.tool_name !== 'plan_update' && parsed.tool_name !== 'create_plan') {
                      recordToolCall(parsed);
                    }
                    const isNestedAgent = parsed.metadata && typeof parsed.metadata.agent === 'string'
                      ? parsed.metadata.agent !== 'orchestrator'
                      : false;
                    if (parsed.content && assistantMessageRef && !parsed.transient && !isNestedAgent && parsed.tool_name !== 'plan_update' && parsed.tool_name !== 'create_plan') {
                      if (!assistantMessageRef.statusLines) assistantMessageRef.statusLines = [];
                      assistantMessageRef.statusLines.push(parsed.content);
                      syncMessages((prev) =>
                        prev.map((msg) =>
                          msg.id === assistantMessageRef?.id ? { ...assistantMessageRef } : msg
                        )
                      );
                    }
                    break;
                  }

                  case 'tool_result': {
                    if (parsed.tool_name !== 'plan_update' && parsed.tool_name !== 'create_plan') {
                      recordToolResult(parsed);
                    }
                    const isNestedAgent = parsed.metadata && typeof parsed.metadata.agent === 'string'
                      ? parsed.metadata.agent !== 'orchestrator'
                      : false;
                    if (parsed.content && assistantMessageRef && !parsed.transient && !isNestedAgent && parsed.tool_name !== 'plan_update' && parsed.tool_name !== 'create_plan') {
                      if (!assistantMessageRef.statusLines) assistantMessageRef.statusLines = [];
                      assistantMessageRef.statusLines.push(parsed.content);
                      syncMessages((prev) =>
                        prev.map((msg) =>
                          msg.id === assistantMessageRef?.id ? { ...assistantMessageRef } : msg
                        )
                      );
                    }
                    break;
                  }

                  case 'thinking':
                    // Show all thinking in Reasoning panel (reasoning_summary, tool-call thinking, ResponseReasoningItem)
                    if (parsed.content && assistantMessageRef) {
                      const prefix = 'Reasoning: ';
                      const isReasoningSummary = parsed.metadata?.kind === 'reasoning_summary';
                      const shouldReset = parsed.metadata?.reset === true;
                      const prevLines = assistantMessageRef.statusLines ? [...assistantMessageRef.statusLines] : [];
                      const lastIndex = prevLines.length - 1;
                      const canAppend =
                        isReasoningSummary &&
                        lastIndex >= 0 &&
                        prevLines[lastIndex].startsWith(prefix) &&
                        !shouldReset;
                      if (canAppend) {
                        prevLines[lastIndex] = `${prevLines[lastIndex]}${parsed.content}`;
                      } else {
                        prevLines.push(`${prefix}${parsed.content}`);
                      }
                      assistantMessageRef.statusLines = prevLines;
                      syncMessages((prev) =>
                        prev.map((msg) =>
                          msg.id === assistantMessageRef?.id ? { ...assistantMessageRef } : msg
                        )
                      );
                    }
                    break;

                  case 'done': {
                    setIsWorkflowComplete(true);
                    // Phase 2: apply backend-generated message_id to assistant message before save
                    const backendMessageId = parsed.message_id;
                    if (
                      typeof backendMessageId === 'string' &&
                      assistantMessageRef
                    ) {
                      const previousId = assistantMessageRef.id;
                      assistantMessageRef.id = backendMessageId;
                      syncMessages((prev) =>
                        prev.map((msg) =>
                          msg.id === previousId
                            ? { ...assistantMessageRef!, id: backendMessageId }
                            : msg
                        )
                      );
                    }
                    if (
                      typeof parsed.final_answer === 'string' &&
                      parsed.final_answer.trim() &&
                      assistantMessageRef &&
                      assistantMessageRef.content.trim() === ''
                    ) {
                      assistantMessageRef.content = parsed.final_answer;
                      syncMessages((prev) =>
                        prev.map((msg) =>
                          msg.id === assistantMessageRef?.id ? { ...assistantMessageRef } : msg
                        )
                      );
                    }
                    await finalizeCompletedWorkflow(trustedSessionId);
                    shouldStopReading = true;
                    break;
                  }

                  case 'error': {
                    const errorText = parsed.error || parsed.content;
                    if (errorText) {
                      toast.error(`Orchestrator error: ${errorText}`);
                      if (assistantMessageRef) {
                        assistantMessageRef.content += `\n\n**Error:** ${errorText}`;
                        syncMessages((prev) =>
                          prev.map((msg) =>
                            msg.id === assistantMessageRef?.id ? { ...assistantMessageRef } : msg
                          )
                        );
                      }
                    }
                    break;
                  }
                }

                if (shouldStopReading) {
                  return { aborted: false };
                }

                // Also handle OpenAI-style streaming format for compatibility
                if (parsed.choices?.[0]?.delta?.content) {
                  const contentDelta = parsed.choices[0].delta.content;
                  if (contentDelta && assistantMessageRef) {
                    assistantMessageRef.content += contentDelta;
                    syncMessages((prev) =>
                      prev.map((msg) =>
                        msg.id === assistantMessageRef?.id ? { ...assistantMessageRef } : msg
                      )
                    );
                  }
                }
              } catch (err) {
                console.warn('Failed to parse SSE data:', data, err);
              }
            }
            return { aborted: false };
          };
          // Periodically persist so statusLines stay fresh while reader.read() blocks.
          // Only enqueue when stage changed since last persist to reduce backlog.
          persistInterval = window.setInterval(() => {
            if (sessionIdRef.current && !deletedSessionIds.has(sessionIdRef.current)) {
              const stage = currentStageRef.current || 'scoping';
              if (stage !== lastPersistedStageRef.current) {
                void persistConversation(stage, false).catch(() => {});
              }
            }
          }, 3000);

          while (!done) {
            if (!isCurrentRequest() || (sessionIdRef.current && deletedSessionIds.has(sessionIdRef.current))) {
              return { ok: false, persisted: false, sessionId: sessionIdRef.current };
            }
            const result = await reader.read();
            if (!isCurrentRequest() || (sessionIdRef.current && deletedSessionIds.has(sessionIdRef.current))) {
              return { ok: false, persisted: false, sessionId: sessionIdRef.current };
            }
            done = result.done || false;
            if (done) break;

            buffer += decoder.decode(result.value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            const parsedResult = await parseSseLines(lines);
            if (parsedResult.aborted) {
              return parsedResult.result;
            }
            if (shouldStopReading) {
              void reader.cancel().catch(() => {});
              break;
            }
          }

          // Flush any pending UTF-8 bytes and parse trailing SSE payload that may
          // not end with a newline boundary.
          if (!shouldStopReading) {
            buffer += decoder.decode();
            if (buffer) {
              const trailingResult = await parseSseLines(buffer.split('\n'));
              if (trailingResult.aborted) {
                return trailingResult.result;
              }
            }
          }
        }
        // Session completion is only when we receive the backend's "done" event.
        // If the stream closes without it, do not finalize (loading still clears in finally).
        return { ok: true, persisted: conversationPersisted, sessionId: persistedSessionId };
      } catch (error) {
        if (!isCurrentRequest()) {
          return { ok: false, persisted: false, sessionId: sessionIdRef.current };
        }
        if (error instanceof DOMException && error.name === 'AbortError') {
          // Stream was intentionally aborted (e.g. navigation away)
          return { ok: false, persisted: false, sessionId: sessionIdRef.current };
        }
        console.error('Orchestrator chat error:', error);
        const status = typeof error === 'object' && error !== null && 'status' in error
          ? Number((error as StreamRequestError).status)
          : undefined;
        const detail = typeof error === 'object' && error !== null && 'detail' in error
          ? (error as StreamRequestError).detail
          : undefined;
        const errorCode = typeof error === 'object' && error !== null && 'errorCode' in error
          ? (error as StreamRequestError).errorCode
          : undefined;
        const isSkaiAuthFailure = (
          status === 401 &&
          (
            errorCode === 'SKAI_AUTH_REQUIRED' ||
            (typeof detail === 'string' && detail.toLowerCase().includes('skai'))
          )
        );

        if (isSkaiAuthFailure) {
          window.dispatchEvent(new CustomEvent('skai-auth-change', { detail: { connected: false } }));
          toast.message(detail || 'SKAI login required. Please reconnect to continue.');
        } else if (status === 401) {
          toast.error(detail || 'Authentication required. Please sign in again.');
        } else {
          toast.error('Failed to send message to orchestrator');
        }
        syncMessages((prev) =>
          prev.filter(
            (msg) => msg.id !== userMessage.id && msg.id !== assistantMessageId
          )
        );
        return { ok: false, persisted: false, sessionId: sessionIdRef.current };
      } finally {
        if (persistInterval !== undefined) {
          window.clearInterval(persistInterval);
        }
        if (abortControllerRef.current === requestController) {
          abortControllerRef.current = null;
        }
        if (activeRequestIdRef.current === requestId) {
          setIsLoading(false);
          setIsStreaming(false);
        }
      }
    },
    [getToken, syncMessages, recordToolCall, recordToolResult, persistConversation, onSessionIdBeforeSend, skaiVersion, filterOptions]
  );

  const clearMessages = useCallback(() => {
    chatContextVersionRef.current += 1;
    cancelActiveStream();
    syncMessages(() => []);
    setPlan(null);
    planRef.current = null;
    setCurrentStage(null);
    setIsWorkflowComplete(false);
    setIsGeneratingReport(false);
    setExecutionLog([]);
    executionLogRef.current = [];
    setCharts([]);
    chartsRef.current = [];
    setConversationId(null);
    setRuntimeSessionId(null);
    sessionIdRef.current = null;
  }, [syncMessages, cancelActiveStream]);

  const clearSession = useCallback(async () => {
    const currentSessionId = sessionIdRef.current;
    // Clear local state immediately so the UI resets before the async server
    // cleanup.  Previously clearMessages() ran *after* the await, which meant
    // navigate('/chat') (in handleNewChat) could be a no-op when we were
    // already on /chat, making "Create new chat" look like a page refresh.
    clearMessages();
    try {
      const token = await getToken();
      if (token && currentSessionId) {
        await fetch(`/api/orchestrator/session/${currentSessionId}`, {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
      }
    } catch (error) {
      console.warn('Failed to clear session on server:', error);
    }
  }, [getToken, clearMessages]);

  const updateMessageFeedback = useCallback(
    (
      assistantMessageId: string,
      feedback: { category: FeedbackCategory; reason?: string } | null
    ) => {
      syncMessages((prev) =>
        prev.map((m) => {
          if (getAssistantMessageId(m) !== assistantMessageId) return m;
          return { ...m, feedback: feedback ?? undefined };
        })
      );
    },
    [syncMessages]
  );

  const markActionSelected = useCallback(
    (messageId: string, action: string) => {
      syncMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, selectedAction: action } : m))
      );
      // Immediately persist so the selection survives chat switches.
      void persistConversation(currentStageRef.current || 'scoping', false).catch(() => {});
    },
    [syncMessages, persistConversation]
  );

  return {
    messages,
    isLoading,
    isStreaming,
    isGeneratingReport,
    currentStage,
    isWorkflowComplete,
    plan,
    executionLog,
    charts,
    sendMessage,
    clearMessages,
    clearSession,
    sessionId: runtimeSessionId,
    conversationId,
    updateMessageFeedback,
    markActionSelected,
  };
}
