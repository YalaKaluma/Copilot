import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { Plus, Trash2, Loader2, Star, Pencil } from 'lucide-react';
import { ChatLeftSidebar } from '../shared/components/layout/ChatLeftSidebar';
import { useChatHistory } from '../features/chat/hooks/useChatHistory';
import { useTemplates } from '../features/chat/hooks/useTemplates';
import { TemplateFormModal } from '../features/chat/components/TemplateFormModal';
import { templateService } from '../features/chat/services/templateService';
import type { TemplateDetail, CreateTemplateRequest, UpdateTemplateRequest } from '../features/chat/types/template.types';

export function TemplatesPage() {
  const navigate = useNavigate();
  const { isLoaded: authLoaded, isSignedIn } = useAuth();
  const [chatHistoryCollapsed, setChatHistoryCollapsed] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<TemplateDetail | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [loadingEditId, setLoadingEditId] = useState<string | null>(null);

  const {
    conversations,
    isLoading: historyLoading,
    fetchHistory,
    selectChat,
    deleteChat,
  } = useChatHistory();

  const {
    templates,
    isLoading: templatesLoading,
    fetchTemplates,
    selectTemplate: _selectTemplate,
    createTemplate,
    updateTemplate,
    deleteTemplate,
  } = useTemplates();

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

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

  const handleUseTemplate = (templateId: string) => {
    navigate('/chat', { state: { templateId } });
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
        <div className="max-w-2xl w-full mx-auto">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-xl font-semibold text-sk-text">Templates</h1>
            <button
              type="button"
              onClick={() => setShowCreateForm(true)}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-sk-accent-red hover:text-sk-accent-red/80 bg-sk-accent-red/10 hover:bg-sk-accent-red/15 transition-colors cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              New template
            </button>
          </div>

          {templatesLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-8 h-8 text-sk-contrast-grey animate-spin" />
            </div>
          ) : templates.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3 rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white p-8">
              <p className="text-sm text-sk-contrast-grey">No templates yet</p>
              <button
                type="button"
                onClick={() => setShowCreateForm(true)}
                className="text-sm font-medium text-sk-accent-red hover:text-sk-accent-red/80 transition-colors cursor-pointer"
              >
                Create your first template
              </button>
            </div>
          ) : (
            <ul className="space-y-2">
              {templates.map((tmpl) => (
                <li
                  key={tmpl.id}
                  className="group flex items-center gap-3 p-4 rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white hover:border-gray-300 dark:hover:border-white/20 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-sk-text truncate">{tmpl.name}</span>
                      {tmpl.isDefault && (
                        <Star className="w-3.5 h-3.5 text-sk-accent-red fill-sk-accent-red flex-shrink-0" />
                      )}
                    </div>
                    {tmpl.description && (
                      <p className="text-xs text-sk-contrast-grey truncate mt-0.5">{tmpl.description}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleUseTemplate(tmpl.id)}
                      className="px-3 py-1.5 text-xs font-medium rounded-lg bg-sk-accent-red/10 text-sk-accent-red hover:bg-sk-accent-red/20 transition-colors cursor-pointer"
                    >
                      Use
                    </button>
                    <button
                      type="button"
                      onClick={async () => {
                        setLoadingEditId(tmpl.id);
                        try {
                          const detail = await templateService.fetchTemplate(tmpl.id);
                          setEditingTemplate(detail);
                        } catch {
                          console.warn('Failed to load template for editing');
                        } finally {
                          setLoadingEditId(null);
                        }
                      }}
                      disabled={loadingEditId === tmpl.id}
                      className="p-2 rounded-lg text-sk-contrast-grey hover:text-sk-text hover:bg-gray-100 dark:hover:bg-white/10 transition-colors cursor-pointer disabled:opacity-50"
                      title="Edit template"
                    >
                      {loadingEditId === tmpl.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Pencil className="w-4 h-4" />
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteTemplate(tmpl.id)}
                      className="p-2 rounded-lg text-sk-contrast-grey hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors cursor-pointer"
                      title="Delete template"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>

      {showCreateForm && (
        <TemplateFormModal
          onSave={async (data) => {
            await createTemplate(data as CreateTemplateRequest);
            setShowCreateForm(false);
          }}
          onClose={() => setShowCreateForm(false)}
        />
      )}
      {editingTemplate && (
        <TemplateFormModal
          template={editingTemplate}
          onSave={async (data) => {
            await updateTemplate(editingTemplate.id, data as UpdateTemplateRequest);
            setEditingTemplate(null);
          }}
          onClose={() => setEditingTemplate(null)}
        />
      )}
    </div>
  );
}

export default TemplatesPage;
