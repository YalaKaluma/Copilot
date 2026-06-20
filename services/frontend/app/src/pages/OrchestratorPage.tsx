import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { Loader2 } from 'lucide-react';
import { motion } from 'motion/react';
import { OrchestratorChatInterface } from '../features/chat/components/OrchestratorChatInterface';
import { ExecutionPlanPanel } from '../features/chat/components/ExecutionPlanPanel';
import { ReasoningPanel } from '../features/chat/components/ReasoningPanel';
import { ReportPanel } from '../features/chat/components/ReportPanel';
import { ChartsPanel } from '../features/chat/components/ChartsPanel';
import { ChatLeftSidebar } from '../shared/components/layout/ChatLeftSidebar';
import { ChatTopBar } from '../shared/components/layout/ChatTopBar';
import { useOrchestratorChat, markSessionDeleted } from '../features/chat/hooks/useOrchestratorChat';
import type { UseChatHistoryReturn } from '../features/chat/hooks/useChatHistory';
import { useFilterOptions } from '../features/chat/hooks/useFilterOptions';
import { cn } from '../shared/utils/cn';
import { useTemplates } from '../features/chat/hooks/useTemplates';
import { apiClient } from '../shared/lib/api-client';
import { config } from '../shared/lib/config';
import { projectService } from '../features/projects';
import type { ConversationDetail } from '../features/chat/types/chatHistory.types';

type RightPanelTab = 'plan_execution' | 'report' | 'charts' | 'reasoning';
const HISTORY_POLL_MS = 5000;
const MIN_LEFT_WIDTH = 240;
const MAX_LEFT_WIDTH = 520;
const MIN_RIGHT_WIDTH = 280;
const MAX_RIGHT_WIDTH = 560;
const MIN_MAIN_WIDTH = 480;

const RIGHT_PANE_TABS: { id: RightPanelTab; label: string }[] = [
  { id: 'reasoning', label: 'Reasoning' },
  { id: 'plan_execution', label: 'Plan & Execution' },
  { id: 'report', label: 'Report' },
  { id: 'charts', label: 'Charts' },
];

interface OrchestratorPageProps {
  sessionId?: string;
  initialConversation?: ConversationDetail;
  hasSessionInUrl?: boolean;
  isHydrating?: boolean;
  projectId?: string;
  projectName?: string;
  /** Chat history state lifted from the wrapper so it survives component remounts. */
  chatHistory: UseChatHistoryReturn;
}

export function OrchestratorPage({
  sessionId,
  initialConversation,
  hasSessionInUrl = true,
  isHydrating = false,
  projectId,
  projectName: projectNameProp,
  chatHistory,
}: OrchestratorPageProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { isLoaded: authLoaded, isSignedIn } = useAuth();
  const [skaiConnected, setSkaiConnected] = useState(false);
  const [skaiStatusKnown, setSkaiStatusKnown] = useState(false);
  const [skaiVersions, setSkaiVersions] = useState<string[]>([]);
  const [skaiVersion, setSkaiVersion] = useState<string | null>(null);
  const [resolvedProjectName, setResolvedProjectName] = useState<string | null>(null);
  const [leftPaneWidth, setLeftPaneWidth] = useState(320);
  const [rightPaneWidth, setRightPaneWidth] = useState(384);
  const [isLargeScreen, setIsLargeScreen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const dragStateRef = useRef<{
    edge: 'left' | 'right';
    startX: number;
    startLeft: number;
    startRight: number;
  } | null>(null);

  const fetchSkaiStatus = useCallback(() => {
    apiClient
      .get<{ connected: boolean }>('/skai/auth/status')
      .then((data) => {
        setSkaiConnected(data.connected);
        setSkaiStatusKnown(true);
      })
      .catch(() => {
        setSkaiConnected(false);
        setSkaiStatusKnown(true);
      });
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const media = window.matchMedia('(min-width: 1024px)');
    const update = () => setIsLargeScreen(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const handleResize = () => {
      const containerWidth = containerRef.current?.clientWidth ?? window.innerWidth;
      const rightVisible = isLargeScreen;
      const availableForLeft = containerWidth - (rightVisible ? rightPaneWidth : 0) - MIN_MAIN_WIDTH;
      if (availableForLeft > 0) {
        const minLeft = Math.min(MIN_LEFT_WIDTH, availableForLeft);
        const maxLeft = Math.min(MAX_LEFT_WIDTH, availableForLeft);
        setLeftPaneWidth((prev) => Math.min(Math.max(prev, minLeft), maxLeft));
      }
      if (rightVisible) {
        const availableForRight = containerWidth - leftPaneWidth - MIN_MAIN_WIDTH;
        if (availableForRight > 0) {
          const minRight = Math.min(MIN_RIGHT_WIDTH, availableForRight);
          const maxRight = Math.min(MAX_RIGHT_WIDTH, availableForRight);
          setRightPaneWidth((prev) => Math.min(Math.max(prev, minRight), maxRight));
        }
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [isLargeScreen, leftPaneWidth, rightPaneWidth]);

  const startResize = useCallback(
    (edge: 'left' | 'right') =>
      (event: React.MouseEvent) => {
        event.preventDefault();
        dragStateRef.current = {
          edge,
          startX: event.clientX,
          startLeft: leftPaneWidth,
          startRight: rightPaneWidth,
        };
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';

        const onMove = (moveEvent: MouseEvent) => {
          const state = dragStateRef.current;
          if (!state) return;
          const containerWidth = containerRef.current?.clientWidth ?? window.innerWidth;
          if (state.edge === 'left') {
            const deltaX = moveEvent.clientX - state.startX;
            const rightVisible = isLargeScreen;
            const available = containerWidth - (rightVisible ? rightPaneWidth : 0) - MIN_MAIN_WIDTH;
            if (available <= 0) return;
            const minLeft = Math.min(MIN_LEFT_WIDTH, available);
            const maxLeft = Math.min(MAX_LEFT_WIDTH, available);
            const next = Math.min(Math.max(state.startLeft + deltaX, minLeft), maxLeft);
            setLeftPaneWidth(next);
          } else {
            const deltaX = moveEvent.clientX - state.startX;
            const available = containerWidth - leftPaneWidth - MIN_MAIN_WIDTH;
            if (available <= 0) return;
            const minRight = Math.min(MIN_RIGHT_WIDTH, available);
            const maxRight = Math.min(MAX_RIGHT_WIDTH, available);
            const next = Math.min(Math.max(state.startRight - deltaX, minRight), maxRight);
            setRightPaneWidth(next);
          }
        };

        const onUp = () => {
          dragStateRef.current = null;
          document.body.style.cursor = '';
          document.body.style.userSelect = '';
          window.removeEventListener('mousemove', onMove);
          window.removeEventListener('mouseup', onUp);
        };

        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
      },
    [isLargeScreen, leftPaneWidth, rightPaneWidth]
  );

  useEffect(() => {
    fetchSkaiStatus();

    const handleAuthChange = (e: Event) => {
      const detail = (e as CustomEvent<{ connected: boolean }>).detail;
      setSkaiConnected(detail.connected);
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchSkaiStatus();
      }
    };
    const pollId = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        fetchSkaiStatus();
      }
    }, 60_000);

    window.addEventListener('skai-auth-change', handleAuthChange);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      window.removeEventListener('skai-auth-change', handleAuthChange);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.clearInterval(pollId);
    };
  }, [fetchSkaiStatus]);

  // Fetch available copilot versions when version selector is enabled (dev + staging)
  useEffect(() => {
    if (config.versionSelectorEnabled && authLoaded && isSignedIn) {
      apiClient
        .get<{ versions: string[] }>('/orchestrator/versions')
        .then((data) => setSkaiVersions(data.versions ?? []))
        .catch(() => setSkaiVersions([]));
    }
  }, [authLoaded, isSignedIn]);

  // Resolve project name when we have projectId but no name (e.g. from ?project=id)
  useEffect(() => {
    if (!projectId || projectNameProp != null) {
      setResolvedProjectName(null);
      return;
    }
    let cancelled = false;
    projectService
      .getProject(projectId)
      .then((p) => {
        if (!cancelled && p) setResolvedProjectName(p.name);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [projectId, projectNameProp]);

  const handleSessionIdBeforeSend = useCallback(
    (id: string) => {
      if (!hasSessionInUrl) {
        const base = location.pathname.replace(/\/$/, '') || '/chat';
        window.history.replaceState(null, '', `${base}/${id}`);
      }
    },
    [hasSessionInUrl, location.pathname]
  );

  const {
    conversations,
    isLoading: historyLoading,
    fetchHistory,
    selectChat,
    deleteChat,
  } = chatHistory;

  const {
    filterOptions,
    filterOptionsLoading,
    selectedFilters,
    toggleFilter,
    clearFilters,
    filtersSectionCollapsed,
    setFiltersSectionCollapsed,
  } = useFilterOptions(skaiVersion);

  const {
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
    clearSession,
    sessionId: runtimeSessionId,
    updateMessageFeedback,
    markActionSelected,
  } = useOrchestratorChat(sessionId, initialConversation, {
    onSessionIdBeforeSend: handleSessionIdBeforeSend,
    skaiVersion: skaiVersion ?? undefined,
    projectId: projectId ?? undefined,
    onTitleGenerated: fetchHistory,
    filterOptions: selectedFilters,
  });

  const {
    templates,
    activeTemplate,
    fetchTemplates,
    selectTemplate,
    clearActiveTemplate,
    createTemplate,
  } = useTemplates();

  // Do not navigate to /chat/:sessionId after first message — avoids remount and chat reload.
  // Conversation is still saved; user can open it from chat history. URL stays /chat until they select a chat.

  const sendMessageWithTemplate = useCallback(async (content: string) => {
    await sendMessage(
      content,
      activeTemplate ? { name: activeTemplate.name, content: activeTemplate.content } : null
    );
  }, [sendMessage, activeTemplate]);

  const handleSelectConversation = useCallback((detail: ConversationDetail) => {
    navigate(`/chat/${detail.sessionId}`, { state: { conversation: detail } });
  }, [navigate]);

  const handleNewChat = useCallback(async () => {
    await clearSession(); // best-effort server cleanup; local state cleared synchronously inside clearSession
    navigate('/chat');
  }, [clearSession, navigate]);

  const showPlan = currentStage === 'execution' || currentStage === 'done' || (plan && Array.isArray((plan as Record<string, unknown>).steps) && ((plan as Record<string, unknown>).steps as unknown[]).length > 0);

  const reasoningSteps = (() => {
    // While a new turn is in-flight and no assistant message has arrived yet, avoid showing stale reasoning.
    const awaitingAssistant = isLoading && messages.length > 0 && messages[messages.length - 1].role === 'user';
    if (awaitingAssistant) return [];
    const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant');
    return lastAssistant?.statusLines ?? [];
  })();

  const [rightPanelTab, setRightPanelTab] = useState<RightPanelTab>('reasoning');
  const [chatHistoryCollapsed, setChatHistoryCollapsed] = useState(false);
  const [loadingSelectedChatId, setLoadingSelectedChatId] = useState<string | null>(null);
  const previousMessagesLengthRef = useRef(messages.length);
  const activeSessionId = runtimeSessionId ?? sessionId ?? null;

  const conversationsForSidebar = useMemo(() => {
    if (!activeSessionId) return conversations;
    return conversations.map((conv) => {
      if (conv.sessionId !== activeSessionId) return conv;
      return {
        ...conv,
        stage: currentStage ?? conv.stage,
        messageCount: Math.max(conv.messageCount, messages.length),
      };
    });
  }, [activeSessionId, conversations, currentStage, messages.length]);

  // Refresh sidebar history when session, message count, or stage changes.
  // Debounced into a single effect so rapid changes (e.g. switching chats)
  // don't fire multiple concurrent fetches whose responses arrive out-of-order.
  const fetchHistoryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    // Track message count changes
    previousMessagesLengthRef.current = messages.length;

    // Debounce: clear any pending fetch, schedule a new one in 300ms
    if (fetchHistoryTimerRef.current) clearTimeout(fetchHistoryTimerRef.current);
    fetchHistoryTimerRef.current = setTimeout(() => {
      fetchHistory();
    }, 300);
    return () => {
      if (fetchHistoryTimerRef.current) clearTimeout(fetchHistoryTimerRef.current);
    };
  }, [sessionId, runtimeSessionId, messages.length, currentStage, fetchHistory]);

  // Poll only history entries (other chats). Active chat is driven by local UI state.
  useEffect(() => {
    const pollHistory = () => {
      if (document.visibilityState === 'visible') {
        void fetchHistory();
      }
    };

    const timer = window.setInterval(pollHistory, HISTORY_POLL_MS);
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        pollHistory();
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [fetchHistory]);

  // Apply template chosen from templates page (navigate with state.templateId)
  useEffect(() => {
    const templateId = (location.state as { templateId?: string } | null)?.templateId;
    if (!templateId) return;
    selectTemplate(templateId);
    navigate(location.pathname, { replace: true, state: {} });
  }, [location.state, location.pathname, navigate, selectTemplate]);

  const handleDeleteChat = useCallback(
    async (id: string) => {
      // Mark the session as deleted so background streams stop persisting it.
      const conv = conversations.find((c) => c.id === id);
      if (conv?.sessionId) {
        markSessionDeleted(conv.sessionId);
      }
      await deleteChat(id);
    },
    [conversations, deleteChat]
  );

  const handleSelectChat = useCallback(
    async (id: string) => {
      setLoadingSelectedChatId(id);
      try {
        const detail = await selectChat(id);
        if (detail) handleSelectConversation(detail);
      } finally {
        setLoadingSelectedChatId(null);
      }
    },
    [selectChat, handleSelectConversation]
  );

  return (
    <div
      ref={containerRef}
      className="flex-1 min-h-0 w-full flex bg-sk-light-grey text-sk-text"
    >
      {/* Left sidebar */}
      <ChatLeftSidebar
        onNewChat={handleNewChat}
        chatHistoryCollapsed={chatHistoryCollapsed}
        onChatHistoryCollapsedChange={setChatHistoryCollapsed}
        conversations={conversationsForSidebar}
        historyLoading={historyLoading}
        onSelectConversation={handleSelectChat}
        onDeleteConversation={handleDeleteChat}
        showChatHistory={authLoaded && isSignedIn}
        width={leftPaneWidth}
        filterOptions={filterOptions}
        filterOptionsLoading={filterOptionsLoading}
        selectedFilters={selectedFilters}
        onToggleFilter={toggleFilter}
        onClearFilters={clearFilters}
        filtersSectionCollapsed={filtersSectionCollapsed}
        onFiltersSectionCollapsedChange={setFiltersSectionCollapsed}
      />

      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize sidebar"
        onMouseDown={startResize('left')}
        className="hidden md:flex w-1.5 cursor-col-resize items-stretch bg-transparent hover:bg-sk-accent-red/20 transition-colors"
      />

      {/* Main chat column (top bar only above chat) + right pane */}
      <div className="flex-1 min-h-0 flex min-w-0">
        {/* Main chat: top bar + chat pane */}
        <div className="flex-1 flex flex-col min-w-0 border-l-2 border-gray-300 dark:border-white/20">
          <ChatTopBar
            skaiConnected={skaiConnected}
            onSkaiAuthChange={fetchSkaiStatus}
            versionSelectorEnabled={config.versionSelectorEnabled}
            versions={skaiVersions}
            selectedVersion={skaiVersion}
            onVersionChange={setSkaiVersion}
            activeProject={
              projectId
                ? { id: projectId, name: projectNameProp ?? resolvedProjectName ?? 'Project' }
                : undefined
            }
          />
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
            className="flex-1 min-h-0 min-w-0 flex flex-col px-4 py-4 overflow-hidden"
          >
            {isWorkflowComplete && isGeneratingReport && (
              <div className="flex-shrink-0 mb-3 px-3 py-2 rounded-lg bg-green-50 dark:bg-green-500/10 border border-green-200 dark:border-green-500/20 text-sm text-green-700 dark:text-green-300">
                Executive report is being generated…
              </div>
            )}
            <OrchestratorChatInterface
              isHydrating={isHydrating && hasSessionInUrl}
              loadingSelectingChat={loadingSelectedChatId !== null}
              messages={messages}
              isLoading={isLoading}
              currentStage={currentStage}
              sendMessage={sendMessageWithTemplate}
              clearSession={handleNewChat}
              skaiConnected={skaiConnected}
              skaiStatusKnown={skaiStatusKnown}
              onSkaiAuthChange={fetchSkaiStatus}
              onUserMessageSent={() => setRightPanelTab('reasoning')}
              onUpdateMessageFeedback={updateMessageFeedback}
              onMarkActionSelected={markActionSelected}
              templates={templates}
              activeTemplate={activeTemplate}
              onFetchTemplates={fetchTemplates}
              onSelectTemplate={selectTemplate}
              onClearTemplate={clearActiveTemplate}
              onCreateTemplate={createTemplate}
            />
          </motion.div>
        </div>

        {/* Right pane - Plan / Execution / Report (hidden on small viewports so chat column is usable) */}
        {/* TODO(chat): Reasoning currently lives in this desktop-only pane. Add a small-screen fallback surface. */}
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize right panel"
          onMouseDown={startResize('right')}
          className="hidden lg:flex w-1.5 cursor-col-resize items-stretch bg-transparent hover:bg-sk-accent-red/20 transition-colors"
        />

        <aside
          className="hidden lg:flex flex-shrink-0 flex-col overflow-hidden bg-sk-light-grey border-l-2 border-gray-300 dark:border-white/20"
          style={{ width: rightPaneWidth }}
        >
            <div className="flex-shrink-0 h-14 flex items-center gap-1 px-4 border-b border-gray-200 dark:border-white/10">
              {RIGHT_PANE_TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setRightPanelTab(tab.id)}
                  className={cn(
                    'px-3 py-2 text-sm font-medium transition-colors cursor-pointer rounded-t',
                    rightPanelTab === tab.id
                      ? 'text-sk-accent-red border-b-2 border-sk-accent-red'
                      : 'text-sk-contrast-grey hover:text-sk-text'
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="flex-1 min-h-0 overflow-auto p-4">
              {rightPanelTab === 'report' && (
                <ReportPanel
                  sessionId={sessionId ?? runtimeSessionId ?? null}
                  reportFromConversation={
                    initialConversation?.sessionId ===
                    (sessionId ?? runtimeSessionId)
                      ? (initialConversation.report ?? undefined)
                      : undefined
                  }
                  isWorkflowComplete={isWorkflowComplete}
                  isStreaming={isStreaming}
                  isGeneratingReport={isGeneratingReport}
                />
              )}
              {rightPanelTab === 'plan_execution' && !showPlan && messages.length === 0 && (
                <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white p-6 text-center">
                  <p className="text-sm text-sk-contrast-grey">
                    Send a message to generate a query plan
                  </p>
                </div>
              )}
              {rightPanelTab === 'plan_execution' && !showPlan && messages.length > 0 && (
                <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white p-6 flex flex-col items-center justify-center gap-3">
                  <Loader2 className="w-6 h-6 text-sk-accent-red animate-spin" />
                  <p className="text-sm text-sk-contrast-grey">
                    Generating query plan…
                  </p>
                </div>
              )}
              {rightPanelTab === 'plan_execution' && showPlan && (
                <ExecutionPlanPanel
                  plan={plan}
                  currentStage={currentStage}
                  isLoading={isLoading}
                  executionLog={executionLog}
                  sessionId={sessionId ?? runtimeSessionId ?? null}
                />
              )}
              {rightPanelTab === 'charts' && (
                <ChartsPanel charts={charts} />
              )}
              {rightPanelTab === 'reasoning' && (
                <ReasoningPanel steps={reasoningSteps} isThinking={isLoading} />
              )}
            </div>
        </aside>
      </div>
    </div>
  );
}

export default OrchestratorPage;
