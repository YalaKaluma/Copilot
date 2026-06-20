import apiClient from '../../../shared/lib/api-client';
import type { ConversationListItem, ConversationDetail } from '../types/chatHistory.types';
import type { ChartItem } from '../types/chart.types';

interface SaveConversationRequest {
  sessionId?: string | null;
  stage: string | null;
  planData: Record<string, unknown> | null;
  executionLog: unknown[] | null;
  charts?: ChartItem[] | null;
  messages: { id: string; role: string; content: string; metadata?: Record<string, unknown> | null }[];
  projectId?: string | null;
}

interface SaveConversationResponse {
  id: string;
  sessionId: string;
  title: string | null;
  stage: string | null;
}

interface GenerateTitleResponse {
  id: string;
  title: string;
}

class ChatHistoryService {
  async fetchConversations(projectId?: string): Promise<ConversationListItem[]> {
    const params = projectId != null ? { project_id: projectId } : undefined;
    return apiClient.get<ConversationListItem[]>('/conversations', { params });
  }

  async fetchConversation(id: string): Promise<ConversationDetail> {
    return apiClient.get<ConversationDetail>(`/conversations/${id}`);
  }

  async fetchConversationBySession(sessionId: string): Promise<ConversationDetail> {
    return apiClient.get<ConversationDetail>(`/conversations/session/${sessionId}`);
  }

  async saveConversation(data: SaveConversationRequest): Promise<SaveConversationResponse> {
    return apiClient.post<SaveConversationResponse>('/conversations', data);
  }

  async deleteConversation(id: string): Promise<void> {
    await apiClient.delete(`/conversations/${id}`);
  }

  async generateTitle(id: string): Promise<GenerateTitleResponse> {
    return apiClient.post<GenerateTitleResponse>(`/conversations/${id}/generate-title`, {});
  }

  async generateReport(
    sessionId: string,
    requirements?: string | null
  ): Promise<ConversationDetail> {
    const body =
      requirements != null && requirements !== ''
        ? { requirements }
        : undefined;
    return apiClient.post<ConversationDetail>(
      `/conversations/session/${sessionId}/generate-report`,
      body ?? {}
    );
  }
}

export const chatHistoryService = new ChatHistoryService();
