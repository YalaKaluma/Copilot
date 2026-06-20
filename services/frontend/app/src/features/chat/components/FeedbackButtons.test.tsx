import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor, waitForElementToBeRemoved } from '@testing-library/react';
import { FeedbackButtons } from './FeedbackButtons';
import { feedbackService } from '../services/feedbackService';
import { toast } from 'sonner';

vi.mock('../services/feedbackService', () => ({
  feedbackService: {
    submitFeedback: vi.fn(),
    deleteFeedback: vi.fn(),
    updateFeedback: vi.fn(),
  },
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockSubmitFeedback = vi.mocked(feedbackService.submitFeedback);
const mockDeleteFeedback = vi.mocked(feedbackService.deleteFeedback);
const mockUpdateFeedback = vi.mocked(feedbackService.updateFeedback);
const mockToastSuccess = vi.mocked(toast.success);
const mockToastError = vi.mocked(toast.error);

describe('FeedbackButtons', () => {
  const assistantMessageId = 'a1b2c3d4-e5f6-4789-a012-3456789abcde';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('use cases', () => {
    it('opens positive popup when thumbs up clicked, then submits with reason', async () => {
      mockSubmitFeedback.mockResolvedValue(undefined);

      render(<FeedbackButtons assistantMessageId={assistantMessageId} />);

      fireEvent.click(screen.getByRole('button', { name: /thumbs up/i }));

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByLabelText(/reason/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^submit$/i })).toBeDisabled();

      fireEvent.change(screen.getByPlaceholderText(/what did you like/i), {
        target: { value: 'Clear and helpful' },
      });
      fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));

      expect(mockSubmitFeedback).toHaveBeenCalledTimes(1);
      expect(mockSubmitFeedback).toHaveBeenCalledWith({
        assistantMessageId,
        category: 'positive',
        reason: 'Clear and helpful',
      });
      await waitFor(() => {
        expect(mockToastSuccess).toHaveBeenCalledWith('Thanks for your feedback!');
      });
    });

    it('opens negative popup when thumbs down clicked, then submits with reason', async () => {
      mockSubmitFeedback.mockResolvedValue(undefined);

      render(<FeedbackButtons assistantMessageId={assistantMessageId} />);

      fireEvent.click(screen.getByRole('button', { name: /thumbs down/i }));

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByLabelText(/reason/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^submit$/i })).toBeDisabled();

      fireEvent.change(screen.getByPlaceholderText(/what went wrong/i), {
        target: { value: 'Wrong answer' },
      });
      fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));

      expect(mockSubmitFeedback).toHaveBeenCalledTimes(1);
      expect(mockSubmitFeedback).toHaveBeenCalledWith({
        assistantMessageId,
        category: 'negative',
        reason: 'Wrong answer',
      });
    });

    it('calls onSubmitted with category and reason when feedback is submitted', async () => {
      mockSubmitFeedback.mockResolvedValue(undefined);
      const onSubmitted = vi.fn();

      render(
        <FeedbackButtons assistantMessageId={assistantMessageId} onSubmitted={onSubmitted} />
      );

      fireEvent.click(screen.getByRole('button', { name: /thumbs up/i }));
      fireEvent.change(screen.getByPlaceholderText(/what did you like/i), {
        target: { value: 'Helpful' },
      });
      fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));

      await waitFor(() => {
        expect(onSubmitted).toHaveBeenCalledWith('positive', 'Helpful');
      });
    });

    it('uses same assistantMessageId in API call as prop (consistency)', () => {
      mockSubmitFeedback.mockResolvedValue(undefined);
      const id = 'b2c3d4e5-f6a7-8901-bcde-f12345678901';

      render(<FeedbackButtons assistantMessageId={id} />);
      fireEvent.click(screen.getByRole('button', { name: /thumbs up/i }));
      fireEvent.change(screen.getByPlaceholderText(/what did you like/i), {
        target: { value: 'Good' },
      });
      fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));

      expect(mockSubmitFeedback).toHaveBeenCalledWith(
        expect.objectContaining({ assistantMessageId: id })
      );
    });
  });

  describe('race condition handling', () => {
    it('only submits once when positive is clicked twice (second click removes)', async () => {
      mockSubmitFeedback.mockResolvedValue(undefined);
      mockDeleteFeedback.mockResolvedValue(undefined);

      render(<FeedbackButtons assistantMessageId={assistantMessageId} />);

      const thumbsUp = screen.getByRole('button', { name: /thumbs up/i });
      await act(async () => {
        fireEvent.click(thumbsUp);
      });
      await act(async () => {
        fireEvent.change(screen.getByPlaceholderText(/what did you like/i), {
          target: { value: 'Good' },
        });
      });
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));
      });
      await act(async () => {
        fireEvent.click(thumbsUp);
      });

      expect(mockSubmitFeedback).toHaveBeenCalledTimes(1);
      expect(mockDeleteFeedback).toHaveBeenCalledTimes(1);
    });

    it('only submits once when negative then positive clicked rapidly (first wins)', async () => {
      mockSubmitFeedback.mockResolvedValue(undefined);

      render(<FeedbackButtons assistantMessageId={assistantMessageId} />);

      fireEvent.click(screen.getByRole('button', { name: /thumbs up/i }));
      fireEvent.change(screen.getByPlaceholderText(/what did you like/i), {
        target: { value: 'Good' },
      });
      fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));
      fireEvent.click(screen.getByRole('button', { name: /thumbs down/i }));

      expect(mockSubmitFeedback).toHaveBeenCalledTimes(1);
      expect(mockSubmitFeedback).toHaveBeenCalledWith(
        expect.objectContaining({ category: 'positive' })
      );
    });

    it('only submits once when negative then positive clicked rapidly (first submit wins)', async () => {
      mockSubmitFeedback.mockResolvedValue(undefined);

      render(<FeedbackButtons assistantMessageId={assistantMessageId} />);

      fireEvent.click(screen.getByRole('button', { name: /thumbs up/i }));
      fireEvent.change(screen.getByPlaceholderText(/what did you like/i), {
        target: { value: 'Good' },
      });
      fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));
      fireEvent.click(screen.getByRole('button', { name: /thumbs down/i }));

      expect(mockSubmitFeedback).toHaveBeenCalledTimes(1);
      expect(mockSubmitFeedback).toHaveBeenCalledWith(
        expect.objectContaining({ category: 'positive' })
      );
    });

    it('shows error toast and does not mark submitted when API rejects', async () => {
      mockSubmitFeedback.mockRejectedValue(new Error('Network error'));

      render(<FeedbackButtons assistantMessageId={assistantMessageId} />);

      fireEvent.click(screen.getByRole('button', { name: /thumbs up/i }));
      fireEvent.change(screen.getByPlaceholderText(/what did you like/i), {
        target: { value: 'Good' },
      });
      fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));

      await waitFor(() => {
        expect(mockSubmitFeedback).toHaveBeenCalledTimes(1);
      });

      expect(mockToastSuccess).not.toHaveBeenCalled();
      expect(mockToastError).toHaveBeenCalledWith('Failed to submit feedback. Please try again.');
    });

    it('calls updateFeedback when switching from positive to negative after submit', async () => {
      mockSubmitFeedback.mockResolvedValue(undefined);
      mockUpdateFeedback.mockResolvedValue(undefined);
      const onUpdated = vi.fn();

      render(
        <FeedbackButtons
          assistantMessageId={assistantMessageId}
          onUpdated={onUpdated}
        />
      );

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /thumbs up/i }));
      });
      await act(async () => {
        fireEvent.change(screen.getByPlaceholderText(/what did you like/i), {
          target: { value: 'Good' },
        });
      });
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));
      });
      expect(mockSubmitFeedback).toHaveBeenCalledTimes(1);

      fireEvent.click(screen.getByRole('button', { name: /thumbs down/i }));
      fireEvent.change(screen.getByPlaceholderText(/what went wrong/i), {
        target: { value: 'Actually wrong' },
      });
      fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));

      expect(mockUpdateFeedback).toHaveBeenCalledWith(assistantMessageId, {
        category: 'negative',
        reason: 'Actually wrong',
      });
      await vi.waitFor(() => {
        expect(onUpdated).toHaveBeenCalledWith('negative', 'Actually wrong');
      });
    });

    it('calls deleteFeedback and onRemoved when same thumb is clicked again', async () => {
      mockSubmitFeedback.mockResolvedValue(undefined);
      mockDeleteFeedback.mockResolvedValue(undefined);
      const onRemoved = vi.fn();

      render(
        <FeedbackButtons
          assistantMessageId={assistantMessageId}
          onRemoved={onRemoved}
        />
      );

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /thumbs up/i }));
      });
      await act(async () => {
        fireEvent.change(screen.getByPlaceholderText(/what did you like/i), {
          target: { value: 'Good' },
        });
      });
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));
      });
      fireEvent.click(screen.getByRole('button', { name: /thumbs up/i }));

      expect(mockDeleteFeedback).toHaveBeenCalledWith(assistantMessageId);
      await vi.waitFor(() => {
        expect(onRemoved).toHaveBeenCalledTimes(1);
      });
    });

    it('reverts and shows error toast when deleteFeedback fails', async () => {
      mockSubmitFeedback.mockResolvedValue(undefined);
      mockDeleteFeedback.mockRejectedValue(new Error('Network error'));
      const onRemoved = vi.fn();

      render(
        <FeedbackButtons
          assistantMessageId={assistantMessageId}
          onRemoved={onRemoved}
        />
      );

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /thumbs up/i }));
      });
      await act(async () => {
        fireEvent.change(screen.getByPlaceholderText(/what did you like/i), {
          target: { value: 'Good' },
        });
      });
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));
      });
      fireEvent.click(screen.getByRole('button', { name: /thumbs up/i }));

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Failed to remove feedback');
      });
      expect(onRemoved).not.toHaveBeenCalled();
      expect(screen.getByRole('button', { name: /thumbs up/i })).toHaveClass(/green/);
    });

    it('reverts and shows error toast when updateFeedback fails', async () => {
      mockSubmitFeedback.mockResolvedValue(undefined);
      mockUpdateFeedback.mockRejectedValue(new Error('Network error'));
      const onUpdated = vi.fn();

      render(
        <FeedbackButtons
          assistantMessageId={assistantMessageId}
          onUpdated={onUpdated}
        />
      );

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /thumbs up/i }));
      });
      await act(async () => {
        fireEvent.change(screen.getByPlaceholderText(/what did you like/i), {
          target: { value: 'Good' },
        });
      });
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));
      });
      fireEvent.click(screen.getByRole('button', { name: /thumbs down/i }));
      fireEvent.change(screen.getByPlaceholderText(/what went wrong/i), {
        target: { value: 'Wrong' },
      });
      fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Failed to update feedback');
      });
      expect(onUpdated).not.toHaveBeenCalled();
      expect(screen.getByRole('button', { name: /thumbs up/i })).toHaveClass(/green/);
    });

    it('does not revert to previous category when PATCH fails late after user already removed feedback', async () => {
      mockSubmitFeedback.mockResolvedValue(undefined);
      mockDeleteFeedback.mockResolvedValue(undefined);
      let rejectUpdate: (err: Error) => void;
      mockUpdateFeedback.mockImplementation(
        () => new Promise((_, rej) => { rejectUpdate = rej; })
      );
      const onRemoved = vi.fn();

      render(
        <FeedbackButtons
          assistantMessageId={assistantMessageId}
          onRemoved={onRemoved}
        />
      );

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /thumbs up/i }));
      });
      await act(async () => {
        fireEvent.change(screen.getByPlaceholderText(/what did you like/i), {
          target: { value: 'Good' },
        });
      });
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));
      });
      await waitFor(() => expect(mockSubmitFeedback).toHaveBeenCalledTimes(1));

      fireEvent.click(screen.getByRole('button', { name: /thumbs down/i }));
      fireEvent.change(screen.getByPlaceholderText(/what went wrong/i), {
        target: { value: 'Wrong' },
      });
      fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));
      expect(mockUpdateFeedback).toHaveBeenCalledTimes(1);

      fireEvent.click(screen.getByRole('button', { name: /thumbs down/i }));
      await waitFor(() => expect(onRemoved).toHaveBeenCalledTimes(1));

      rejectUpdate!(new Error('Late PATCH failure'));
      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Failed to update feedback');
      });

      expect(screen.getByRole('button', { name: /thumbs up/i })).not.toHaveClass(/bg-green-100/);
    });

    it('does not revert to previous category when DELETE fails late after user already switched feedback', async () => {
      mockSubmitFeedback.mockResolvedValue(undefined);
      let rejectDelete: (err: Error) => void;
      mockDeleteFeedback.mockImplementation(
        () => new Promise((_, rej) => { rejectDelete = rej; })
      );
      const onSubmitted = vi.fn();

      render(
        <FeedbackButtons
          assistantMessageId={assistantMessageId}
          onSubmitted={onSubmitted}
        />
      );

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /thumbs up/i }));
      });
      await act(async () => {
        fireEvent.change(screen.getByPlaceholderText(/what did you like/i), {
          target: { value: 'Good' },
        });
      });
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));
      });
      await waitFor(() => expect(mockSubmitFeedback).toHaveBeenCalledTimes(1));

      fireEvent.click(screen.getByRole('button', { name: /thumbs up/i }));
      expect(mockDeleteFeedback).toHaveBeenCalledTimes(1);

      fireEvent.click(screen.getByRole('button', { name: /thumbs down/i }));
      fireEvent.change(screen.getByPlaceholderText(/what went wrong/i), {
        target: { value: 'Actually wrong' },
      });
      fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));
      await waitFor(() => expect(mockSubmitFeedback).toHaveBeenCalledTimes(2));
      await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith('negative', 'Actually wrong'));

      rejectDelete!(new Error('Late DELETE failure'));
      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Failed to remove feedback');
      });

      expect(screen.getByRole('button', { name: /thumbs down/i })).toHaveClass(/red/);
    });
  });

  describe('feedback popup', () => {
    it('submit button is disabled until reason is entered', () => {
      render(<FeedbackButtons assistantMessageId={assistantMessageId} />);

      fireEvent.click(screen.getByRole('button', { name: /thumbs down/i }));
      expect(screen.getByRole('button', { name: /^submit$/i })).toBeDisabled();

      fireEvent.change(screen.getByPlaceholderText(/what went wrong/i), {
        target: { value: '   ' },
      });
      expect(screen.getByRole('button', { name: /^submit$/i })).toBeDisabled();

      fireEvent.change(screen.getByPlaceholderText(/what went wrong/i), {
        target: { value: ' Bad answer' },
      });
      expect(screen.getByRole('button', { name: /^submit$/i })).not.toBeDisabled();
    });

    it('trims reason before sending', () => {
      mockSubmitFeedback.mockResolvedValue(undefined);

      render(<FeedbackButtons assistantMessageId={assistantMessageId} />);

      fireEvent.click(screen.getByRole('button', { name: /thumbs down/i }));
      fireEvent.change(screen.getByPlaceholderText(/what went wrong/i), {
        target: { value: '  trimmed  ' },
      });
      fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));

      expect(mockSubmitFeedback).toHaveBeenCalledWith({
        assistantMessageId,
        category: 'negative',
        reason: 'trimmed',
      });
    });

    it('cancel closes popup without submitting', async () => {
      render(<FeedbackButtons assistantMessageId={assistantMessageId} />);

      fireEvent.click(screen.getByRole('button', { name: /thumbs down/i }));
      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /cancel/i }));

      await waitForElementToBeRemoved(dialog, { timeout: 2000 });
      expect(mockSubmitFeedback).not.toHaveBeenCalled();
    });
  });

  describe('initialSubmitted (restored from past conversation)', () => {
    it('shows positive state when initialSubmitted is positive', () => {
      render(
        <FeedbackButtons
          assistantMessageId={assistantMessageId}
          initialSubmitted="positive"
        />
      );

      const thumbsUp = screen.getByRole('button', { name: /thumbs up/i });
      expect(thumbsUp).toHaveClass(/green/);
    });

    it('shows negative state when initialSubmitted is negative', () => {
      render(
        <FeedbackButtons
          assistantMessageId={assistantMessageId}
          initialSubmitted="negative"
        />
      );

      const thumbsDown = screen.getByRole('button', { name: /thumbs down/i });
      expect(thumbsDown).toHaveClass(/red/);
    });

    it('re-clicking thumbs down removes feedback when initialSubmitted is negative', async () => {
      mockDeleteFeedback.mockResolvedValue(undefined);
      const onRemoved = vi.fn();

      render(
        <FeedbackButtons
          assistantMessageId={assistantMessageId}
          initialSubmitted="negative"
          onRemoved={onRemoved}
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /thumbs down/i }));

      expect(mockDeleteFeedback).toHaveBeenCalledWith(assistantMessageId);
      await vi.waitFor(() => {
        expect(onRemoved).toHaveBeenCalledTimes(1);
      });
    });
  });
});
