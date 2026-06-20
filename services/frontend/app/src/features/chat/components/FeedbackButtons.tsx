import type { KeyboardEvent } from 'react';
import { useEffect, useState } from 'react';
import { Loader2, ThumbsDown, ThumbsUp } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { toast } from 'sonner';
import { cn } from '../../../shared/utils/cn';
import { feedbackService } from '../services/feedbackService';
import type { FeedbackCategory } from '../services/feedbackService';

export interface FeedbackButtonsProps {
  assistantMessageId: string;
  /** Initial feedback state when message was restored from a past conversation. */
  initialSubmitted?: FeedbackCategory | null;
  onSubmitted?: (category: FeedbackCategory, reason: string) => void;
  onUpdated?: (category: FeedbackCategory, reason: string) => void;
  onRemoved?: () => void;
}

export function FeedbackButtons({
  assistantMessageId,
  initialSubmitted = null,
  onSubmitted,
  onUpdated,
  onRemoved,
}: FeedbackButtonsProps) {
  const [submitted, setSubmitted] = useState<FeedbackCategory | null>(
    initialSubmitted ?? null
  );
  const [popupOpen, setPopupOpen] = useState(false);
  const [popupCategory, setPopupCategory] = useState<'positive' | 'negative' | null>(null);
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setSubmitted(initialSubmitted ?? null);
  }, [initialSubmitted]);

  const closePopup = () => {
    setPopupOpen(false);
    setPopupCategory(null);
    setReason('');
  };

  const submitFeedback = async (category: FeedbackCategory, reasonValue: string) => {
    if (submitted) return;
    const trimmedReason = reasonValue.trim();
    if (!trimmedReason) return;

    setIsSubmitting(true);
    try {
      await feedbackService.submitFeedback({
        assistantMessageId,
        category,
        reason: trimmedReason,
      });
      setSubmitted(category);
      onSubmitted?.(category, trimmedReason);
      closePopup();
      toast.success('Thanks for your feedback!');
    } catch {
      toast.error('Failed to submit feedback. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const updateFeedback = (category: FeedbackCategory, reasonValue: string) => {
    if (!submitted) return;
    const trimmedReason = reasonValue.trim();
    if (!trimmedReason) return;

    const previous = submitted;
    setSubmitted(category);
    closePopup();
    feedbackService
      .updateFeedback(assistantMessageId, { category, reason: trimmedReason })
      .then(() => {
        onUpdated?.(category, trimmedReason);
      })
      .catch(() => {
        setSubmitted((current) => (current === category ? previous : current));
        toast.error('Failed to update feedback');
      });
  };

  const removeFeedback = () => {
    if (!submitted) return;
    const previous = submitted;
    setSubmitted(null);
    void feedbackService
      .deleteFeedback(assistantMessageId)
      .then(() => {
        onRemoved?.();
      })
      .catch(() => {
        setSubmitted((current) => (current === null ? previous : current));
        toast.error('Failed to remove feedback');
      });
  };

  const openPositivePopup = () => {
    setPopupCategory('positive');
    setReason('');
    setPopupOpen(true);
  };

  const openNegativePopup = () => {
    if (submitted === 'negative') {
      removeFeedback();
      return;
    }
    setPopupCategory('negative');
    setReason('');
    setPopupOpen(true);
  };

  const handlePositiveClick = () => {
    if (!submitted) {
      openPositivePopup();
      return;
    }
    if (submitted === 'positive') {
      removeFeedback();
      return;
    }
    openPositivePopup();
  };

  const handleSubmitFromPopup = () => {
    const trimmed = reason.trim();
    if (!trimmed || !popupCategory) return;
    if (!submitted) {
      submitFeedback(popupCategory, trimmed);
    } else {
      updateFeedback(popupCategory, trimmed);
    }
  };

  const handleReasonKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (canSubmit) handleSubmitFromPopup();
    }
  };

  const canSubmit = reason.trim().length > 0 && !isSubmitting;
  const dialogTitle =
    popupCategory === 'positive'
      ? 'What did you like about this response?'
      : "What didn't you like?";

  return (
    <>
      <div className="flex items-center gap-1 mt-2" aria-label="Rate this response">
        <button
          type="button"
          onClick={handlePositiveClick}
          className={cn(
            'p-1.5 rounded-md transition-colors',
            submitted === 'positive'
              ? 'text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/30'
              : 'text-gray-400 hover:text-green-600 hover:bg-gray-100 dark:hover:bg-green-900/20'
          )}
          aria-label="Thumbs up"
        >
          <ThumbsUp className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={openNegativePopup}
          className={cn(
            'p-1.5 rounded-md transition-colors',
            submitted === 'negative'
              ? 'text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/30'
              : 'text-gray-400 hover:text-red-600 hover:bg-gray-100 dark:hover:bg-red-900/20'
          )}
          aria-label="Thumbs down"
        >
          <ThumbsDown className="w-3.5 h-3.5" />
        </button>
      </div>

      <AnimatePresence>
        {popupOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/40 z-40"
              onClick={closePopup}
              aria-hidden
            />
            <motion.div
              role="dialog"
              aria-labelledby="feedback-dialog-title"
              aria-modal
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              transition={{ duration: 0.15 }}
              className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-sm rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white dark:bg-gray-900 shadow-lg p-4"
              onClick={(e) => e.stopPropagation()}
            >
              <h2 id="feedback-dialog-title" className="text-sm font-semibold text-sk-text mb-3">
                {dialogTitle}
              </h2>
              <label
                htmlFor="feedback-reason"
                className="block text-xs text-gray-500 dark:text-gray-400 mb-1.5"
              >
                Reason (required)
              </label>
              <textarea
                id="feedback-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                onKeyDown={handleReasonKeyDown}
                placeholder={
                  popupCategory === 'positive'
                    ? 'What did you like? (Enter to submit)'
                    : 'What went wrong? (Enter to submit)'
                }
                rows={3}
                className="w-full rounded-lg border border-gray-200 dark:border-white/10 bg-transparent px-3 py-2 text-sm text-sk-text placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-sk-accent-red/30 focus:border-sk-accent-red resize-none mb-4"
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={closePopup}
                  className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300 hover:text-sk-text rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSubmitFromPopup}
                  disabled={!canSubmit}
                  className="px-3 py-1.5 text-sm font-medium rounded-lg transition-colors cursor-pointer bg-sk-accent-red hover:bg-sk-accent-red/90 text-white disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Submitting...
                    </>
                  ) : (
                    'Submit'
                  )}
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
