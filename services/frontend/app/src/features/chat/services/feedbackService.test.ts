import { describe, it, expect, vi, beforeEach } from 'vitest';
import { feedbackService } from './feedbackService';
import apiClient from '../../../shared/lib/api-client';

vi.mock('../../../shared/lib/api-client', () => ({
  default: {
    post: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  },
}));

describe('feedbackService', () => {
  beforeEach(() => {
    vi.mocked(apiClient.post).mockReset();
    vi.mocked(apiClient.delete).mockReset();
    vi.mocked(apiClient.patch).mockReset();
  });

  describe('submitFeedback', () => {
    it('calls POST /orchestrator/feedback with assistantMessageId, category and reason', async () => {
      vi.mocked(apiClient.post).mockResolvedValue(undefined as never);

      await feedbackService.submitFeedback({
        assistantMessageId: 'a1b2c3d4-e5f6-4789-a012-3456789abcde',
        category: 'positive',
        reason: 'Clear and helpful',
      });

      expect(apiClient.post).toHaveBeenCalledTimes(1);
      expect(apiClient.post).toHaveBeenCalledWith('/orchestrator/feedback', {
        assistantMessageId: 'a1b2c3d4-e5f6-4789-a012-3456789abcde',
        category: 'positive',
        reason: 'Clear and helpful',
      });
    });

    it('sends negative category and reason correctly', async () => {
      vi.mocked(apiClient.post).mockResolvedValue(undefined as never);

      await feedbackService.submitFeedback({
        assistantMessageId: 'b2c3d4e5-f6a7-8901-bcde-f12345678901',
        category: 'negative',
        reason: 'Wrong answer',
      });

      expect(apiClient.post).toHaveBeenCalledWith('/orchestrator/feedback', {
        assistantMessageId: 'b2c3d4e5-f6a7-8901-bcde-f12345678901',
        category: 'negative',
        reason: 'Wrong answer',
      });
    });

    it('rejects when API throws', async () => {
      vi.mocked(apiClient.post).mockRejectedValue(new Error('Network error'));

      await expect(
        feedbackService.submitFeedback({
          assistantMessageId: 'a1b2c3d4-e5f6-4789-a012-3456789abcde',
          category: 'positive',
          reason: 'Good',
        })
      ).rejects.toThrow('Network error');

      expect(apiClient.post).toHaveBeenCalledTimes(1);
    });

    it('uses same assistantMessageId in payload as passed in (consistency)', async () => {
      vi.mocked(apiClient.post).mockResolvedValue(undefined as never);
      const id = 'c3d4e5f6-a7b8-9012-cdef-123456789012';

      await feedbackService.submitFeedback({
        assistantMessageId: id,
        category: 'positive',
        reason: 'Helpful',
      });

      const call = vi.mocked(apiClient.post).mock.calls[0];
      expect(call?.[1]).toMatchObject({
        assistantMessageId: id,
        category: 'positive',
        reason: 'Helpful',
      });
    });
  });

  describe('deleteFeedback', () => {
    it('calls DELETE /orchestrator/feedback/{id} with assistantMessageId', async () => {
      vi.mocked(apiClient.delete).mockResolvedValue(undefined as never);
      const id = 'a1b2c3d4-e5f6-4789-a012-3456789abcde';

      await feedbackService.deleteFeedback(id);

      expect(apiClient.delete).toHaveBeenCalledTimes(1);
      expect(apiClient.delete).toHaveBeenCalledWith(
        '/orchestrator/feedback/a1b2c3d4-e5f6-4789-a012-3456789abcde'
      );
    });

    it('rejects when API throws', async () => {
      vi.mocked(apiClient.delete).mockRejectedValue(new Error('Network error'));

      await expect(
        feedbackService.deleteFeedback('a1b2c3d4-e5f6-4789-a012-3456789abcde')
      ).rejects.toThrow('Network error');
    });
  });

  describe('updateFeedback', () => {
    it('calls PATCH /orchestrator/feedback/{id} with category and reason', async () => {
      vi.mocked(apiClient.patch).mockResolvedValue(undefined as never);
      const id = 'a1b2c3d4-e5f6-4789-a012-3456789abcde';

      await feedbackService.updateFeedback(id, {
        category: 'negative',
        reason: 'Changed mind',
      });

      expect(apiClient.patch).toHaveBeenCalledTimes(1);
      expect(apiClient.patch).toHaveBeenCalledWith(
        '/orchestrator/feedback/a1b2c3d4-e5f6-4789-a012-3456789abcde',
        { category: 'negative', reason: 'Changed mind' }
      );
    });

    it('sends reason only when updating comment (no category change)', async () => {
      vi.mocked(apiClient.patch).mockResolvedValue(undefined as never);

      await feedbackService.updateFeedback('b2c3d4e5-f6a7-8901-bcde-f12345678901', {
        reason: 'Updated comment',
      });

      expect(apiClient.patch).toHaveBeenCalledWith(
        '/orchestrator/feedback/b2c3d4e5-f6a7-8901-bcde-f12345678901',
        { reason: 'Updated comment' }
      );
    });

    it('rejects when API throws', async () => {
      vi.mocked(apiClient.patch).mockRejectedValue(new Error('Network error'));

      await expect(
        feedbackService.updateFeedback('a1b2c3d4-e5f6-4789-a012-3456789abcde', {
          category: 'negative',
          reason: 'Changed mind',
        })
      ).rejects.toThrow('Network error');
    });
  });
});
