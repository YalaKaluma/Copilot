import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { ChatLeftSidebar } from '../shared/components/layout/ChatLeftSidebar';
import { useChatHistory } from '../features/chat/hooks/useChatHistory';
import { chatHistoryService } from '../features/chat/services/chatHistoryService';
import { ChartRenderer } from '../features/chat/components/ChartRenderer';
import { useProjects } from '../features/projects';
import { MessageSquare, FileText, BarChart3, FileBarChart, ArrowLeft, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '../shared/utils/cn';
import type { ConversationListItem } from '../features/chat/types/chatHistory.types';
import type { ChartItem } from '../features/chat/types/chart.types';

type TabId = 'chat' | 'files' | 'charts' | 'report';

const TABS: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'files', label: 'Files', icon: FileText },
  { id: 'charts', label: 'Charts', icon: BarChart3 },
  { id: 'report', label: 'Report', icon: FileBarChart },
];

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { isLoaded: authLoaded, isSignedIn } = useAuth();
  const [chatHistoryCollapsed, setChatHistoryCollapsed] = useState(false);
  const initialTab = (location.state as { tab?: TabId } | null)?.tab ?? 'chat';
  const [activeTab, setActiveTab] = useState<TabId>(initialTab);

  const { getProject, projects: _projects, fetchProjects } = useProjects();
  const [projectName, setProjectName] = useState<string | null>(null);
  const [projectLoading, setProjectLoading] = useState(true);
  const [projectError, setProjectError] = useState(false);

  const {
    conversations,
    isLoading: historyLoading,
    fetchHistory,
    selectChat,
    deleteChat,
  } = useChatHistory(projectId ?? undefined);

  const [chartsByConversation, setChartsByConversation] = useState<
    Record<string, { title: string; charts: ChartItem[] }>
  >({});
  const [chartsLoading, setChartsLoading] = useState(false);
  const chartsLoadedIdsRef = useRef<Set<string>>(new Set());

  const conversationsWithCharts = conversations.filter((c) => c.hasCharts);

  const conversationIdsWithCharts = conversationsWithCharts.map((c) => c.id).join(',');
  const conversationsWithChartsRef = useRef(conversationsWithCharts);
  conversationsWithChartsRef.current = conversationsWithCharts;

  useEffect(() => {
    if (activeTab !== 'charts') return;
    const list = conversationsWithChartsRef.current;
    if (list.length === 0) return;
    const toLoad = list.filter((c) => !chartsLoadedIdsRef.current.has(c.id));
    if (toLoad.length === 0) return;
    setChartsLoading(true);
    Promise.all(toLoad.map((c) => chatHistoryService.fetchConversation(c.id)))
      .then((details) => {
        setChartsByConversation((prev) => {
          const next = { ...prev };
          toLoad.forEach((conv, i) => {
            chartsLoadedIdsRef.current.add(conv.id);
            const detail = details[i];
            if (detail?.charts && detail.charts.length > 0) {
              const charts: ChartItem[] = detail.charts.map((ch, j) => ({
                id: ch.id ?? `chart-${conv.id}-${j}`,
                title: ch.title ?? '',
                chartType: ch.chartType ?? 'bar',
                data: ch.data ?? [],
              }));
              next[conv.id] = { title: conv.title ?? 'Untitled chat', charts };
            }
          });
          return next;
        });
      })
      .finally(() => setChartsLoading(false));
  }, [activeTab, conversationIdsWithCharts]);

  useEffect(() => {
    chartsLoadedIdsRef.current = new Set();
    setChartsByConversation({});
  }, [projectId]);

  const [selectedReport, setSelectedReport] = useState<{
    conversationId: string;
    title: string;
    report: string;
  } | null>(null);
  const [selectedReportLoading, setSelectedReportLoading] = useState(false);

  const handleSelectReport = (conversationId: string, title: string) => {
    setSelectedReportLoading(true);
    setSelectedReport(null);
    chatHistoryService
      .fetchConversation(conversationId)
      .then((detail) => {
        setSelectedReport({
          conversationId,
          title: title || 'Untitled chat',
          report: detail.report ?? '',
        });
      })
      .catch(() => {
        setSelectedReport(null);
      })
      .finally(() => setSelectedReportLoading(false));
  };

  const handleCloseReport = () => {
    setSelectedReport(null);
  };

  useEffect(() => {
    if (!projectId) {
      setProjectError(true);
      setProjectLoading(false);
      return;
    }
    let cancelled = false;
    setProjectLoading(true);
    setProjectError(false);
    getProject(projectId)
      .then((p) => {
        if (!cancelled && p) {
          setProjectName(p.name);
        } else if (!cancelled) {
          setProjectError(true);
        }
      })
      .catch(() => {
        if (!cancelled) setProjectError(true);
      })
      .finally(() => {
        if (!cancelled) setProjectLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, getProject]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    if (projectId) {
      fetchHistory();
    }
  }, [projectId, fetchHistory]);

  const handleNewChat = () => {
    if (projectId) {
      navigate('/chat', { state: { projectId, projectName: projectName ?? undefined } });
    } else {
      navigate('/chat');
    }
  };

  const handleSelectChat = (id: string) => {
    selectChat(id).then((detail) => {
      if (detail?.sessionId) {
        navigate(`/chat/${detail.sessionId}`, {
          state: {
            conversation: detail,
            projectId: projectId ?? undefined,
            projectName: projectName ?? undefined,
          },
        });
      }
    });
  };

  const handleBack = () => {
    navigate('/chat/projects');
  };

  if (!projectId) {
    navigate('/chat/projects', { replace: true });
    return null;
  }

  if (projectError) {
    return (
      <div className="flex-1 min-h-0 flex items-center justify-center text-sk-contrast-grey">
        <p>Project not found.</p>
        <button
          type="button"
          onClick={() => navigate('/chat/projects')}
          className="ml-2 text-sk-accent-red hover:underline"
        >
          Back to projects
        </button>
      </div>
    );
  }

  return (
    <div className="flex-1 min-h-0 w-full flex bg-sk-light-grey text-sk-text">
      <ChatLeftSidebar
        onNewChat={handleNewChat}
        chatHistoryCollapsed={chatHistoryCollapsed}
        onChatHistoryCollapsedChange={setChatHistoryCollapsed}
        conversations={conversations}
        historyLoading={historyLoading}
        onSelectConversation={handleSelectChat}
        onDeleteConversation={deleteChat}
        showChatHistory={authLoaded && isSignedIn}
      />

      <main className="flex-1 min-h-0 flex flex-col min-w-0 overflow-hidden border-l-2 border-gray-300 dark:border-white/20">
        {/* Header */}
        <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-white/10">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={handleBack}
              className="p-1.5 rounded-lg text-sk-contrast-grey hover:text-sk-text hover:bg-white/5 transition-colors"
              aria-label="Back to projects"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            {projectLoading ? (
              <Loader2 className="w-5 h-5 animate-spin text-sk-contrast-grey" />
            ) : (
              <h1 className="text-xl font-semibold text-sk-text truncate">
                {projectName ?? 'Project'}
              </h1>
            )}
          </div>
          <button
            type="button"
            onClick={handleNewChat}
            className="flex-shrink-0 px-4 py-2 rounded-lg bg-sk-accent-red text-white font-medium hover:opacity-90 transition-opacity"
          >
            + New Chat
          </button>
        </div>

        {/* Tabs */}
        <div className="flex-shrink-0 flex gap-1 px-6 pt-2 border-b border-gray-200 dark:border-white/10">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setActiveTab(id)}
              className={cn(
                'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors',
                activeTab === id
                  ? 'border-sk-accent-red text-sk-accent-red'
                  : 'border-transparent text-sk-contrast-grey hover:text-sk-text'
              )}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 min-h-0 overflow-auto px-6 py-6">
          {activeTab === 'chat' && (
            <ChatTab
              projectName={projectName ?? 'Project'}
              conversations={conversations}
              isLoading={historyLoading}
              onSelectConversation={handleSelectChat}
            />
          )}
          {activeTab === 'files' && (
            <div className="max-w-2xl">
              <p className="text-sk-contrast-grey">Coming soon. Project files will appear here.</p>
            </div>
          )}
          {activeTab === 'charts' && (
            <ChartsTab
              conversationsWithCharts={conversationsWithCharts}
              chartsByConversation={chartsByConversation}
              chartsLoading={chartsLoading}
              onSelectConversation={handleSelectChat}
            />
          )}
          {activeTab === 'report' && (
            <ReportTab
              conversations={conversations}
              selectedReport={selectedReport}
              selectedReportLoading={selectedReportLoading}
              onSelectReport={handleSelectReport}
              onCloseReport={handleCloseReport}
              onOpenInChat={handleSelectChat}
            />
          )}
        </div>
      </main>
    </div>
  );
}

function ChatTab({
  projectName,
  conversations,
  isLoading,
  onSelectConversation,
}: {
  projectName: string;
  conversations: ConversationListItem[];
  isLoading: boolean;
  onSelectConversation: (id: string) => void;
}) {
  return (
    <div className="max-w-2xl">
      <h2 className="text-base font-semibold text-sk-text mb-4">
        Previous conversations in {projectName}
      </h2>
      {isLoading && conversations.length === 0 ? (
        <div className="flex items-center gap-2 text-sk-contrast-grey py-8">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Loading conversations…</span>
        </div>
      ) : conversations.length === 0 ? (
        <p className="text-sk-contrast-grey py-8">No conversations yet. Start a new chat above.</p>
      ) : (
        <ul className="space-y-2">
          {conversations.map((conv) => (
            <li key={conv.id}>
              <button
                type="button"
                onClick={() => onSelectConversation(conv.id)}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-200 dark:border-white/10 text-left hover:bg-white/5 transition-colors"
              >
                <MessageSquare className="w-5 h-5 flex-shrink-0 text-sk-contrast-grey" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-sk-text truncate">
                    {conv.title || 'Untitled chat'}
                  </p>
                  <p className="text-xs text-sk-contrast-grey mt-0.5">
                    {conv.messageCount} message{conv.messageCount !== 1 ? 's' : ''}
                  </p>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ChartsTab({
  conversationsWithCharts,
  chartsByConversation,
  chartsLoading,
  onSelectConversation,
}: {
  conversationsWithCharts: ConversationListItem[];
  chartsByConversation: Record<string, { title: string; charts: ChartItem[] }>;
  chartsLoading: boolean;
  onSelectConversation: (id: string) => void;
}) {
  const entries = conversationsWithCharts
    .map((c) => {
      const data = chartsByConversation[c.id];
      return data ? { id: c.id, title: data.title, charts: data.charts } : null;
    })
    .filter((e): e is { id: string; title: string; charts: ChartItem[] } => e != null);

  return (
    <div className="max-w-3xl">
      <h2 className="text-base font-semibold text-sk-text mb-2">Charts in this project</h2>
      <p className="text-sm text-sk-contrast-grey mb-4">
        Charts from conversations in this project. Click a conversation title to open it in chat.
      </p>
      {conversationsWithCharts.length === 0 ? (
        <p className="text-sk-contrast-grey py-4">
          No charts yet. Generate charts in a conversation, then they will appear here.
        </p>
      ) : chartsLoading && entries.length === 0 ? (
        <div className="flex items-center gap-2 text-sk-contrast-grey py-8">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Loading charts…</span>
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {entries.map(({ id, title, charts }) => (
            <section key={id} className="rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white overflow-hidden">
              <button
                type="button"
                onClick={() => onSelectConversation(id)}
                className="w-full flex items-center gap-2 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-white/5 transition-colors border-b border-gray-200 dark:border-white/10"
              >
                <BarChart3 className="w-4 h-4 flex-shrink-0 text-sk-contrast-grey" />
                <span className="text-sm font-medium text-sk-text truncate">{title}</span>
              </button>
              <div className="p-4 flex flex-col gap-4">
                {charts.map((chart) => (
                  <div
                    key={chart.id}
                    className="rounded-lg border border-gray-200 dark:border-white/10 p-4 bg-gray-50/50 dark:bg-white/5"
                  >
                    <div className="flex items-start gap-3 mb-3">
                      <div className="w-8 h-8 rounded-lg bg-gray-200 dark:bg-white/10 flex items-center justify-center flex-shrink-0">
                        <BarChart3 className="w-4 h-4 text-sk-contrast-grey" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className="text-sm font-semibold text-sk-text">{chart.title}</h3>
                        <p className="text-xs text-sk-contrast-grey capitalize">{chart.chartType} chart</p>
                      </div>
                    </div>
                    <div className="min-h-[200px]">
                      <ChartRenderer chart={chart} height={220} />
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

function ReportTab({
  conversations,
  selectedReport,
  selectedReportLoading,
  onSelectReport,
  onCloseReport,
  onOpenInChat,
}: {
  conversations: ConversationListItem[];
  selectedReport: { conversationId: string; title: string; report: string } | null;
  selectedReportLoading: boolean;
  onSelectReport: (conversationId: string, title: string) => void;
  onCloseReport: () => void;
  onOpenInChat: (id: string) => void;
}) {
  const withReport = conversations.filter((c) => c.hasReport);

  if (selectedReport) {
    return (
      <div className="max-w-3xl">
        <div className="flex items-center justify-between gap-3 mb-4">
          <button
            type="button"
            onClick={onCloseReport}
            className="flex items-center gap-2 text-sm font-medium text-sk-contrast-grey hover:text-sk-text transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to reports
          </button>
          <button
            type="button"
            onClick={() => onOpenInChat(selectedReport.conversationId)}
            className="text-sm font-medium text-sk-accent-red hover:underline"
          >
            Open in chat
          </button>
        </div>
        <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white overflow-hidden shadow-sm">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-white/10">
            <h2 className="text-base font-semibold text-sk-text truncate" title={selectedReport.title}>
              {selectedReport.title}
            </h2>
            <p className="text-xs text-sk-contrast-grey mt-0.5">Executive summary</p>
          </div>
          <div className="p-4 text-sm text-sk-text leading-relaxed prose prose-sm dark:prose-invert max-w-none">
            {selectedReport.report ? (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  h1: ({ children }) => <h1 className="text-lg font-bold mt-3 mb-2">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-base font-bold mt-3 mb-1.5">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>,
                  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                  ul: ({ children }) => <ul className="list-disc pl-5 mb-2 space-y-0.5">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal pl-5 mb-2 space-y-0.5">{children}</ol>,
                  li: ({ children }) => <li>{children}</li>,
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-3 border-gray-300 dark:border-white/20 pl-3 my-2 italic">
                      {children}
                    </blockquote>
                  ),
                }}
              >
                {selectedReport.report}
              </ReactMarkdown>
            ) : (
              <p className="text-sk-contrast-grey">No report content.</p>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      <h2 className="text-base font-semibold text-sk-text mb-2">Reports in this project</h2>
      <p className="text-sm text-sk-contrast-grey mb-4">
        Conversations that have a report. Click to view the report on this page.
      </p>
      {withReport.length === 0 ? (
        <p className="text-sk-contrast-grey py-4">
          No reports yet. Generate a report in a conversation (Report tab in the right panel), then it will appear here.
        </p>
      ) : selectedReportLoading ? (
        <div className="flex items-center gap-2 text-sk-contrast-grey py-8">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Loading report…</span>
        </div>
      ) : (
        <ul className="space-y-2">
          {withReport.map((conv) => (
            <li key={conv.id}>
              <button
                type="button"
                onClick={() => onSelectReport(conv.id, conv.title ?? 'Untitled chat')}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-200 dark:border-white/10 text-left hover:bg-white/5 transition-colors"
              >
                <FileBarChart className="w-5 h-5 flex-shrink-0 text-sk-contrast-grey" />
                <span className="text-sm font-medium text-sk-text truncate">
                  {conv.title || 'Untitled chat'}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
