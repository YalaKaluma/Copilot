import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { ChatLeftSidebar } from '../shared/components/layout/ChatLeftSidebar';
import { useChatHistory } from '../features/chat/hooks/useChatHistory';
import { useProjects } from '../features/projects';
import { MessageSquare, FileText, BarChart3, Plus, Loader2, Trash2 } from 'lucide-react';
import { cn } from '../shared/utils/cn';

const CARD_COLORS = [
  'bg-sky-900/80',
  'bg-slate-800',
  'bg-teal-900/80',
  'bg-amber-900/80',
  'bg-rose-900/80',
  'bg-indigo-900/80',
];

function getProjectColor(index: number): string {
  return CARD_COLORS[index % CARD_COLORS.length];
}

function getInitial(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return '?';
  return trimmed.charAt(0).toUpperCase();
}

export function ProjectsPage() {
  const navigate = useNavigate();
  const { isLoaded: authLoaded, isSignedIn } = useAuth();
  const [chatHistoryCollapsed, setChatHistoryCollapsed] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDescription, setNewProjectDescription] = useState('');

  const {
    projects,
    isLoading: projectsLoading,
    fetchProjects,
    createProject,
    deleteProject,
  } = useProjects();

  const {
    conversations,
    isLoading: historyLoading,
    fetchHistory,
    selectChat,
    deleteChat,
  } = useChatHistory();

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleNewChat = () => {
    navigate('/chat');
  };

  const handleSelectChat = (id: string) => {
    selectChat(id).then((detail) => {
      if (detail?.sessionId) {
        navigate(`/chat/${detail.sessionId}`, { state: { conversation: detail } });
      }
    });
  };

  const handleDeleteProject = async (e: React.MouseEvent, projectId: string) => {
    e.stopPropagation();
    await deleteProject(projectId);
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = newProjectName.trim();
    if (!name || isCreating) return;
    setIsCreating(true);
    try {
      const project = await createProject({ name, description: newProjectDescription.trim() || undefined });
      if (project) {
        setNewProjectName('');
        setNewProjectDescription('');
        setShowCreateForm(false);
        navigate(`/chat/projects/${project.id}`);
      }
    } finally {
      setIsCreating(false);
    }
  };

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

      <main className="flex-1 min-h-0 flex flex-col min-w-0 px-6 py-6 overflow-auto border-l-2 border-gray-300 dark:border-white/20">
        <div className="max-w-4xl w-full mx-auto">
          <h1 className="text-xl font-semibold text-sk-text">Projects</h1>

          {projectsLoading ? (
            <div className="mt-6 flex items-center gap-2 text-sk-contrast-grey">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Loading projects…</span>
            </div>
          ) : (
            <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* Add project card */}
              {showCreateForm ? (
                <form
                  onSubmit={handleCreateProject}
                  className="rounded-xl border-2 border-dashed border-gray-300 dark:border-white/20 p-6 flex flex-col gap-3 bg-white/5"
                >
                  <input
                    type="text"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    placeholder="Project name"
                    disabled={isCreating}
                    className="w-full px-3 py-2 rounded-lg bg-white/10 border border-gray-300 dark:border-white/20 text-sk-text placeholder:text-sk-contrast-grey focus:outline-none focus:ring-2 focus:ring-sk-accent-red/50 disabled:opacity-60 disabled:cursor-not-allowed"
                    autoFocus
                  />
                  <input
                    type="text"
                    value={newProjectDescription}
                    onChange={(e) => setNewProjectDescription(e.target.value)}
                    placeholder="Description (optional)"
                    disabled={isCreating}
                    className="w-full px-3 py-2 rounded-lg bg-white/10 border border-gray-300 dark:border-white/20 text-sk-text placeholder:text-sk-contrast-grey focus:outline-none focus:ring-2 focus:ring-sk-accent-red/50 disabled:opacity-60 disabled:cursor-not-allowed"
                  />
                  <div className="flex gap-2">
                    <button
                      type="submit"
                      disabled={isCreating}
                      className="px-3 py-1.5 rounded-lg bg-sk-accent-red text-white text-sm font-medium hover:opacity-90 disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-2"
                    >
                      {isCreating ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Creating…
                        </>
                      ) : (
                        'Create'
                      )}
                    </button>
                    <button
                      type="button"
                      disabled={isCreating}
                      onClick={() => {
                        setShowCreateForm(false);
                        setNewProjectName('');
                        setNewProjectDescription('');
                      }}
                      className="px-3 py-1.5 rounded-lg bg-white/10 text-sk-text text-sm hover:bg-white/20 disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <button
                  type="button"
                  onClick={() => setShowCreateForm(true)}
                  className={cn(
                    'rounded-xl border-2 border-dashed border-gray-300 dark:border-white/20 p-6',
                    'flex flex-col items-center justify-center gap-2 min-h-[160px]',
                    'text-sk-contrast-grey hover:text-sk-text hover:border-sk-accent-red/50 hover:bg-white/5 transition-colors'
                  )}
                >
                  <Plus className="w-10 h-10" />
                  <span className="text-sm font-medium">Add project</span>
                </button>
              )}

              {projects.map((project, index) => (
                <div
                  key={project.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => navigate(`/chat/projects/${project.id}`)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      navigate(`/chat/projects/${project.id}`);
                    }
                  }}
                  className="rounded-xl border border-gray-200 dark:border-white/10 overflow-hidden bg-white/5 hover:bg-white/10 transition-colors cursor-pointer"
                >
                  <div
                    className={cn(
                      'h-24 flex items-center justify-center text-3xl font-bold text-white/90',
                      getProjectColor(index)
                    )}
                  >
                    {getInitial(project.name)}
                  </div>
                  <div className="p-4">
                    <h3 className="font-semibold text-sk-text truncate" title={project.name}>
                      {project.name}
                    </h3>
                    <div className="mt-3 flex flex-wrap gap-3 text-sm" onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        onClick={() => navigate(`/chat/projects/${project.id}`)}
                        className="flex items-center gap-1.5 text-sk-contrast-grey hover:text-sk-accent-red transition-colors"
                      >
                        <MessageSquare className="w-4 h-4" />
                        Chat History
                      </button>
                      <button
                        type="button"
                        onClick={() => navigate(`/chat/projects/${project.id}`, { state: { tab: 'files' } })}
                        className="flex items-center gap-1.5 text-sk-contrast-grey hover:text-sk-accent-red transition-colors"
                      >
                        <FileText className="w-4 h-4" />
                        Files
                      </button>
                      <button
                        type="button"
                        onClick={() => navigate(`/chat/projects/${project.id}`, { state: { tab: 'charts' } })}
                        className="flex items-center gap-1.5 text-sk-contrast-grey hover:text-sk-accent-red transition-colors"
                      >
                        <BarChart3 className="w-4 h-4" />
                        Charts
                      </button>
                      <button
                        type="button"
                        onClick={(e) => handleDeleteProject(e, project.id)}
                        className="flex items-center gap-1.5 text-sk-contrast-grey hover:text-red-500 transition-colors ml-auto"
                        title="Delete project"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
