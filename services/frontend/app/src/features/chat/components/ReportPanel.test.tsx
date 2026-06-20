import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { toast } from 'sonner';
import { ReportPanel } from './ReportPanel';
import { reportMarkdownToPlainText } from '../utils/reportCopy';

vi.mock('../services/chatHistoryService', () => ({
  chatHistoryService: {
    fetchConversationBySession: vi.fn(),
    generateReport: vi.fn(),
  },
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe('ReportPanel copy summary', () => {
  const writeText = vi.fn();
  const mockToastSuccess = vi.mocked(toast.success);
  const mockToastError = vi.mocked(toast.error);

  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(globalThis.navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    });
  });

  it('copies converted plain text and shows success toast', async () => {
    const report = `# Executive Summary
Revenue grew by **12%**.

- Strong conversion
1. Expand in Q2

See [details](https://example.com).`;
    writeText.mockResolvedValue(undefined);

    render(
      <ReportPanel
        sessionId="session-1"
        reportFromConversation={report}
        isWorkflowComplete
      />
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Copy summary' }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(reportMarkdownToPlainText(report));
      expect(mockToastSuccess).toHaveBeenCalledWith('Executive summary copied');
    });
  });

  it('shows error toast when clipboard copy fails', async () => {
    writeText.mockRejectedValue(new Error('clipboard unavailable'));

    render(
      <ReportPanel
        sessionId="session-1"
        reportFromConversation="Executive summary body."
        isWorkflowComplete
      />
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Copy summary' }));

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('Failed to copy executive summary');
    });
  });

  it('does not show copy button when there is no report', () => {
    render(
      <ReportPanel
        sessionId="session-1"
        reportFromConversation={null}
        isWorkflowComplete
      />
    );

    expect(screen.queryByRole('button', { name: 'Copy summary' })).not.toBeInTheDocument();
  });
});
