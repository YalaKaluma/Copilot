import { useState, useCallback, useRef } from 'react';
import { toast } from 'sonner';
import { logger } from '../../../shared/lib/logger';
import { chatHistoryService } from '../services/chatHistoryService';
import type { ConversationListItem, ConversationDetail } from '../types/chatHistory.types';

const log = logger.create('ChatHistory');

export interface UseChatHistoryReturn {
  conversations: ConversationListItem[];
  isLoading: boolean;
  fetchHistory: () => Promise<void>;
  deleteChat: (id: string) => Promise<void>;
  selectChat: (id: string) => Promise<ConversationDetail | null>;
}

/**
 * @param projectId When set, only conversations for this project are fetched and shown.
 */
export function useChatHistory(projectId?: string): UseChatHistoryReturn {
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const latestFetchRequestIdRef = useRef(0);

  // Retain previous list while loading; only replace on successful fetch (never clear on refetch).
  const fetchHistory = useCallback(async () => {
    const requestId = latestFetchRequestIdRef.current + 1;
    latestFetchRequestIdRef.current = requestId;
    setIsLoading(true);
    try {
      const data = await chatHistoryService.fetchConversations(projectId);
      if (requestId === latestFetchRequestIdRef.current) {
        setConversations(data);
      }
    } catch (error) {
      if (requestId === latestFetchRequestIdRef.current) {
        log.error('Failed to fetch chat history:', error);
        toast.error('Failed to load chat history');
      }
      // Keep previous conversations on error; do not clear
    } finally {
      if (requestId === latestFetchRequestIdRef.current) {
        setIsLoading(false);
      }
    }
  }, [projectId]);

  const deleteChat = useCallback(async (id: string) => {
    // Optimistic removal
    setConversations((prev) => prev.filter((c) => c.id !== id));
    try {
      await chatHistoryService.deleteConversation(id);
    } catch (error) {
      log.error('Failed to delete conversation:', error);
      toast.error('Failed to delete conversation');
      // Re-fetch to restore correct state (same scope as current)
      await fetchHistory();
    }
  }, [fetchHistory]);

  const selectChat = useCallback(async (id: string): Promise<ConversationDetail | null> => {
    try {
      return await chatHistoryService.fetchConversation(id);
    } catch (error) {
      log.error('Failed to load conversation:', error);
      toast.error('Failed to load conversation');
      return null;
    }
  }, []);

  return {
    conversations,
    isLoading,
    fetchHistory,
    deleteChat,
    selectChat,
  };
}
