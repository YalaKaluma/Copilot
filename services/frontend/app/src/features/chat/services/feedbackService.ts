import apiClient from '../../../shared/lib/api-client';

export type FeedbackCategory = 'positive' | 'negative';

interface SubmitFeedbackRequest {
  assistantMessageId: string;
  category: FeedbackCategory;
  /** Required: non-empty after trim. */
  reason: string;
}

export interface UpdateFeedbackRequest {
  category?: FeedbackCategory;
  reason?: string | null;
}

class FeedbackService {
  async submitFeedback(data: SubmitFeedbackRequest): Promise<void> {
    await apiClient.post('/orchestrator/feedback', data);
  }

  async deleteFeedback(assistantMessageId: string): Promise<void> {
    await apiClient.delete(`/orchestrator/feedback/${assistantMessageId}`);
  }

  async updateFeedback(
    assistantMessageId: string,
    data: UpdateFeedbackRequest
  ): Promise<void> {
    await apiClient.patch(`/orchestrator/feedback/${assistantMessageId}`, data);
  }
}

export const feedbackService = new FeedbackService();
