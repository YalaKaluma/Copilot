import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useParams, useLocation, useNavigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { OrchestratorPage } from './pages/OrchestratorPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { ProjectDetailPage } from './pages/ProjectDetailPage';
import { TemplatesPage } from './pages/TemplatesPage';
import { UserAccountPage } from './pages/UserAccountPage';
import ClerkProvider from './shared/providers/ClerkProvider';
import ProtectedRoute from './features/auth/components/ProtectedRoute';
import AuthToastHandler from './features/auth/components/AuthToastHandler';
import AppLayout from './shared/components/layout/AppLayout';
import useApiClient from './shared/hooks/useApiClient';
import { ThemeProvider } from './shared/providers/ThemeProvider';
import type { ConversationDetail } from './features/chat/types/chatHistory.types';
import { chatHistoryService } from './features/chat/services/chatHistoryService';
import { useChatHistory } from './features/chat/hooks/useChatHistory';

function OrchestratorPageWrapper() {
  const { sessionId: routeSessionId } = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const stateConversation = location.state?.conversation as ConversationDetail | undefined;
  const projectIdFromState = location.state?.projectId as string | undefined;
  const projectNameFromState = location.state?.projectName as string | undefined;
  const projectIdFromSearch = new URLSearchParams(location.search).get('project');
  const projectId = projectIdFromState ?? projectIdFromSearch ?? undefined;
  const projectName = projectNameFromState ?? undefined;
  const [conversation, setConversation] = useState<ConversationDetail | undefined>(
    stateConversation
  );
  const [isHydrating, setIsHydrating] = useState(false);
  const hasSessionInUrl = Boolean(routeSessionId);

  useEffect(() => {
    let isCancelled = false;
    let latestRequestId = 0;

    const fetchConversation = async () => {
      if (!routeSessionId || isCancelled) return;
      const requestId = latestRequestId + 1;
      latestRequestId = requestId;
      try {
        const detail = await chatHistoryService.fetchConversationBySession(routeSessionId);
        if (isCancelled || requestId !== latestRequestId) return;
        // Prefer navigation state's "done" so we don't regress stage when fetch returns stale data.
        const stateDone = stateConversation?.sessionId === routeSessionId && stateConversation?.stage === 'done';
        const merged = stateDone && detail.stage !== 'done' ? { ...detail, stage: 'done' as const } : detail;
        setConversation(merged);
        setIsHydrating(false);
      } catch (error: unknown) {
        const status = (error as { status?: number })?.status;
        if (isCancelled || requestId !== latestRequestId) return;
        setConversation(undefined);
        if (status === 404) {
          navigate('/chat', { replace: true });
          return;
        }
        console.warn('Failed to hydrate conversation by session:', error);
        setIsHydrating(false);
      }
    };

    if (!routeSessionId) {
      setConversation(undefined);
      setIsHydrating(false);
      return () => {
        isCancelled = true;
      };
    }

    const haveConversationForSession = stateConversation?.sessionId === routeSessionId;
    setConversation(haveConversationForSession ? stateConversation : undefined);
    // Only show main-pane loading when we don't already have this conversation (e.g. page refresh). If we have it (e.g. from navigation state), don't refresh the main pane.
    setIsHydrating(!haveConversationForSession);

    void fetchConversation();

    return () => {
      isCancelled = true;
    };
  }, [routeSessionId, stateConversation, navigate]);

  // Chat history lives here (above the keyed OrchestratorPage) so the sidebar
  // conversation list survives component remounts when switching chats.
  const chatHistory = useChatHistory(projectId);

  return (
    <OrchestratorPage
      key={routeSessionId ?? 'draft'}
      sessionId={routeSessionId}
      initialConversation={hasSessionInUrl && conversation?.sessionId === routeSessionId ? conversation : undefined}
      hasSessionInUrl={hasSessionInUrl}
      isHydrating={isHydrating}
      projectId={projectId}
      projectName={projectName}
      chatHistory={chatHistory}
    />
  );
}

function AppContent() {
  // Initialize API client with Clerk authentication
  useApiClient();

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<OrchestratorPageWrapper />} />
            <Route path="/chat/projects" element={<ProjectsPage />} />
            <Route path="/chat/projects/:projectId" element={<ProjectDetailPage />} />
            <Route path="/chat/templates" element={<TemplatesPage />} />
            <Route path="/chat/:sessionId" element={<OrchestratorPageWrapper />} />
            <Route path="/growth-copilot" element={<OrchestratorPageWrapper />} />
            <Route path="/growth-copilot/:sessionId" element={<OrchestratorPageWrapper />} />
            <Route path="/user" element={<UserAccountPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Route>
      </Routes>
      <Toaster
        position="top-right"
        richColors
        closeButton
        toastOptions={{
          duration: 4000,
          style: {
            borderRadius: '12px',
            padding: '16px',
            fontSize: '14px',
          },
        }}
      />
    </BrowserRouter>
  );
}

function App() {
  return (
    <ThemeProvider defaultTheme="light" storageKey="vite-ui-theme">
      <ClerkProvider>
        <AuthToastHandler>
          <AppContent />
        </AuthToastHandler>
      </ClerkProvider>
    </ThemeProvider>
  );
}

export default App;
