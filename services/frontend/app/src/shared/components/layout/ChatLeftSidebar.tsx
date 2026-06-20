import { useState, useEffect } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { Plus, FolderOpen, LayoutTemplate, ChevronDown, Trash2, Loader2 } from 'lucide-react';
import { cn } from '../../utils/cn';
import { StageBadge } from '../../../features/chat/components/StageIndicators';
import { FilterPanel } from '../../../features/chat/components/FilterPanel';
import type { ConversationListItem } from '../../../features/chat/types/chatHistory.types';
import type { FilterOptions, SelectedFilters } from '../../../features/chat/types/filters.types';

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

const CHAT_HISTORY_PAGE_SIZE = 10;

export interface ChatLeftSidebarProps {
  onNewChat: () => void;
  chatHistoryCollapsed: boolean;
  onChatHistoryCollapsedChange: (collapsed: boolean) => void;
  conversations: ConversationListItem[];
  historyLoading: boolean;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  /** When false, the Chat History section is hidden (e.g. when user is not signed in). */
  showChatHistory?: boolean;
  width?: number;
  /** When provided, a collapsible "Show filters" section is rendered below Chat History. */
  filterOptions?: FilterOptions;
  filterOptionsLoading?: boolean;
  selectedFilters?: SelectedFilters;
  onToggleFilter?: (key: string, value: string) => void;
  onClearFilters?: () => void;
  filtersSectionCollapsed?: boolean;
  onFiltersSectionCollapsedChange?: (collapsed: boolean) => void;
}

export function ChatLeftSidebar({
  onNewChat,
  chatHistoryCollapsed,
  onChatHistoryCollapsedChange,
  conversations,
  historyLoading,
  onSelectConversation,
  onDeleteConversation,
  showChatHistory = true,
  width,
  filterOptions,
  filterOptionsLoading = false,
  selectedFilters = {},
  onToggleFilter,
  onClearFilters,
  filtersSectionCollapsed = true,
  onFiltersSectionCollapsedChange,
}: ChatLeftSidebarProps) {
  const [visibleCount, setVisibleCount] = useState(CHAT_HISTORY_PAGE_SIZE);
  const visibleConversations = conversations.slice(0, visibleCount);
  const hasMore = conversations.length > visibleCount;

  useEffect(() => {
    if (visibleCount > CHAT_HISTORY_PAGE_SIZE && visibleCount > conversations.length) {
      setVisibleCount((_prev) => Math.max(CHAT_HISTORY_PAGE_SIZE, conversations.length));
    }
  }, [conversations.length, visibleCount]);

  return (
    <aside
      className={cn('flex-shrink-0 flex flex-col bg-sk-light-grey', width == null && 'w-80')}
      style={width != null ? { width } : undefined}
    >
      {/* Logo */}
      <div className="h-14 flex items-center px-4 border-b border-gray-200 dark:border-white/10">
        <Link
          to="/chat"
          className="flex items-center gap-3 hover:opacity-90 transition-opacity min-w-0"
          onClick={(e) => {
            e.preventDefault();
            onNewChat();
          }}
        >
          <img
            src="/sk-logo-small.png"
            alt="SKAI"
            className="h-9 w-auto flex-shrink-0"
          />
          <span className="text-base font-semibold text-sk-text whitespace-nowrap min-w-0 truncate">
            <span className="text-sk-accent-red">SKAI</span>{' '}
            <span className="text-sk-text font-normal">Growth Copilot</span>
          </span>
        </Link>
      </div>

      {/* Nav */}
      <nav className="p-3 flex-1 flex flex-col min-h-0 gap-2">
        <button
          type="button"
          onClick={onNewChat}
          className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-base text-sk-contrast-grey hover:text-sk-text hover:bg-white/5 transition-colors cursor-pointer text-left w-full"
        >
          <Plus className="w-4 h-4 flex-shrink-0" />
          New Chat
        </button>
        <NavLink
          to="/chat/projects"
          className={({ isActive }) =>
            cn(
              'flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-base transition-colors cursor-pointer text-left w-full',
              isActive ? 'text-sk-accent-red bg-sk-accent-red/10' : 'text-sk-contrast-grey hover:text-sk-text hover:bg-white/5'
            )
          }
        >
          <FolderOpen className="w-4 h-4 flex-shrink-0" />
          Projects
        </NavLink>
        <NavLink
          to="/chat/templates"
          className={({ isActive }) =>
            cn(
              'flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-base transition-colors cursor-pointer text-left w-full',
              isActive ? 'text-sk-accent-red bg-sk-accent-red/10' : 'text-sk-contrast-grey hover:text-sk-text hover:bg-white/5'
            )
          }
        >
          <LayoutTemplate className="w-4 h-4 flex-shrink-0" />
          Templates
        </NavLink>

        {/* Chat History - collapsible list; hidden when not signed in */}
        {showChatHistory && (
        <div className="mt-4 pt-4 flex-1 flex flex-col min-h-0 border-t border-gray-200 dark:border-white/10">
          <button
            type="button"
            onClick={() => onChatHistoryCollapsedChange(!chatHistoryCollapsed)}
            className="flex items-center justify-between w-full px-3 py-2 text-sm font-medium uppercase tracking-wider text-sk-contrast-grey hover:text-sk-text transition-colors cursor-pointer flex-shrink-0"
          >
            <span className="flex items-center gap-2">
              Chat History
              {historyLoading && (
                <Loader2 className="w-3.5 h-3.5 text-sk-contrast-grey animate-spin flex-shrink-0" aria-hidden />
              )}
            </span>
            <ChevronDown
              className={cn(
                'w-4 h-4 flex-shrink-0 transition-transform',
                !chatHistoryCollapsed && 'rotate-180'
              )}
            />
          </button>
          {!chatHistoryCollapsed && (
            <div className="flex-1 overflow-y-auto min-h-0 mt-1">
              {historyLoading && conversations.length === 0 ? (
                <div className="flex justify-center py-6">
                  <Loader2 className="w-5 h-5 text-sk-contrast-grey animate-spin" />
                </div>
              ) : conversations.length === 0 ? (
                <p className="px-3 py-4 text-xs text-sk-contrast-grey">No chats yet — start a new one!</p>
              ) : (
                <div className="space-y-0.5 py-1">
                  {visibleConversations.map((conv) => (
                    <div
                      key={conv.id}
                      className="group flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
                      onClick={() => onSelectConversation(conv.id)}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-sk-text truncate">
                          {conv.title || 'Untitled chat'}
                        </p>
                        <div className="flex items-center gap-2 mt-0.5">
                          {conv.stage && conv.stage !== 'done' && (
                            <StageBadge stage={conv.stage} />
                          )}
                          <span className="text-[10px] text-sk-contrast-grey">
                            {timeAgo(conv.updatedAt)}
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteConversation(conv.id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-white/10 text-sk-contrast-grey hover:text-red-500 transition-all cursor-pointer flex-shrink-0"
                        title="Delete conversation"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                  {hasMore && (
                    <button
                      type="button"
                      onClick={() => setVisibleCount((prev) => prev + CHAT_HISTORY_PAGE_SIZE)}
                      className="w-full px-3 py-2 text-xs font-medium text-sk-contrast-grey hover:text-sk-text hover:bg-white/5 rounded-lg transition-colors cursor-pointer"
                    >
                      Load more
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
        )}
        {filterOptions !== undefined && onToggleFilter && onClearFilters && onFiltersSectionCollapsedChange && (
          <FilterPanel
            filterOptions={filterOptions}
            filterOptionsLoading={filterOptionsLoading}
            selectedFilters={selectedFilters}
            onToggleFilter={onToggleFilter}
            onClearFilters={onClearFilters}
            collapsed={filtersSectionCollapsed}
            onCollapsedChange={onFiltersSectionCollapsedChange}
          />
        )}
      </nav>
    </aside>
  );
}
