import { useCallback, useEffect, useRef, useState } from 'react';
import { FileText, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ReportPlaceholderCard } from './ReportPlaceholderCard';
import { chatHistoryService } from '../services/chatHistoryService';
import { reportMarkdownToPlainText } from '../utils/reportCopy';

interface ReportPanelProps {
  sessionId: string | null;
  /** When provided (including null), use this instead of fetching – e.g. report from conversation loaded by parent. */
  reportFromConversation?: string | null;
  /** When true, session is done; when false, workflow is in progress. */
  isWorkflowComplete?: boolean;
  /** Stream state from orchestrator; used as a refetch trigger after completion/background generation. */
  isStreaming?: boolean;
  /** True while backend auto-generates report after final response. */
  isGeneratingReport?: boolean;
}

export function ReportPanel({
  sessionId,
  reportFromConversation,
  isWorkflowComplete = false,
  isStreaming = false,
  isGeneratingReport = false,
}: ReportPanelProps) {
  const [report, setReport] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [isManualGenerating, setIsManualGenerating] = useState(false);
  const [requirements, setRequirements] = useState('');
  const [error, setError] = useState<string | null>(null);
  const isGenerating = isManualGenerating || isGeneratingReport;
  const hasTriggeredAutoGenerateRef = useRef<string | null>(null);
  const hasCompletedLoadForSessionRef = useRef<string | null>(null);

  const fetchReport = useCallback(() => {
    if (!sessionId || reportFromConversation !== undefined) return;
    setLoading(true);
    setError(null);
    hasCompletedLoadForSessionRef.current = null;
    chatHistoryService
      .fetchConversationBySession(sessionId)
      .then((detail) => {
        setReport(detail.report ?? null);
      })
      .catch((err) => {
        if (err?.response?.status === 404) {
          setReport(null);
          setError('No conversation for this session.');
        } else {
          setError('Failed to load conversation.');
        }
      })
      .finally(() => {
        setLoading(false);
        hasCompletedLoadForSessionRef.current = sessionId;
      });
  }, [sessionId, reportFromConversation]);

  // When parent provides conversation data (e.g. from history), use it and skip fetch.
  useEffect(() => {
    if (!sessionId) {
      setReport(null);
      setError(null);
      hasTriggeredAutoGenerateRef.current = null;
      hasCompletedLoadForSessionRef.current = null;
      return;
    }
    if (reportFromConversation !== undefined) {
      setReport(reportFromConversation ?? null);
      setError(null);
      hasCompletedLoadForSessionRef.current = sessionId;
      return;
    }
    fetchReport();
  }, [
    sessionId,
    reportFromConversation,
    isWorkflowComplete,
    isStreaming,
    isGeneratingReport,
    fetchReport,
  ]);

  // Fallback: when session is done but no report yet (e.g. auto-trigger missed), start generation once.
  // Only run after we've completed loading (fetch or reportFromConversation) and confirmed no report, so we don't regenerate when just switching to the tab.
  useEffect(() => {
    if (
      !sessionId ||
      !isWorkflowComplete ||
      reportFromConversation !== undefined ||
      report ||
      loading ||
      isGenerating ||
      hasTriggeredAutoGenerateRef.current === sessionId ||
      hasCompletedLoadForSessionRef.current !== sessionId
    ) {
      return;
    }
    hasTriggeredAutoGenerateRef.current = sessionId;
    setIsManualGenerating(true);
    chatHistoryService
      .generateReport(sessionId)
      .then((detail) => {
        setReport(detail.report ?? null);
      })
      .catch(() => {
        toast.error('Failed to generate report');
        hasTriggeredAutoGenerateRef.current = null;
      })
      .finally(() => setIsManualGenerating(false));
  }, [sessionId, isWorkflowComplete, reportFromConversation, report, loading, isGenerating]);

  const handleGenerateReport = () => {
    if (!sessionId) return;
    setIsManualGenerating(true);
    chatHistoryService
      .generateReport(sessionId, requirements.trim() || undefined)
      .then((detail) => {
        setReport(detail.report ?? null);
        setRequirements('');
      })
      .catch(() => {
        toast.error('Failed to generate report');
      })
      .finally(() => setIsManualGenerating(false));
  };

  const handleCopySummary = () => {
    if (!report?.trim()) return;
    navigator.clipboard
      .writeText(reportMarkdownToPlainText(report))
      .then(() => {
        toast.success('Executive summary copied');
      })
      .catch(() => {
        toast.error('Failed to copy executive summary');
      });
  };

  // 1. New chat: placeholder only, no generate button
  if (!sessionId) {
    return (
      <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white p-4 shadow-sm">
        <ReportPlaceholderCard />
      </div>
    );
  }

  // 2. Ongoing chat: message only, no button, no loading
  if (!isWorkflowComplete) {
    return (
      <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white p-4 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-white/10 flex items-center justify-center flex-shrink-0">
            <FileText className="w-5 h-5 text-sk-contrast-grey" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-sk-text mb-1">Executive Summary</h3>
            <p className="text-xs text-sk-contrast-grey leading-relaxed">
              Executive summary will be generated at the end of current session.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // 3. Final answer state: show loading only when we're actually fetching (not in ongoing)
  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white p-6 flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-6 h-6 text-sk-accent-red animate-spin" />
        <p className="text-sm text-sk-contrast-grey">Loading…</p>
      </div>
    );
  }

  // 3b. Report is being generated: loading dots
  if (isGenerating) {
    return (
      <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white p-6 flex flex-col items-center justify-center gap-3">
        <p className="text-sm text-sk-contrast-grey inline-flex items-center">
          Executive summary is being generated
          <span className="inline-flex gap-0.5 ml-1" aria-hidden>
            <span
              className="w-1.5 h-1.5 rounded-full bg-current animate-[loading-dots_1.2s_ease-in-out_infinite]"
              style={{ animationDelay: '0ms' }}
            />
            <span
              className="w-1.5 h-1.5 rounded-full bg-current animate-[loading-dots_1.2s_ease-in-out_infinite]"
              style={{ animationDelay: '200ms' }}
            />
            <span
              className="w-1.5 h-1.5 rounded-full bg-current animate-[loading-dots_1.2s_ease-in-out_infinite]"
              style={{ animationDelay: '400ms' }}
            />
          </span>
        </p>
      </div>
    );
  }

  // 3c. Has report: show report (markdown) + requirements + Re-generate button
  if (report) {
    return (
      <div className="space-y-4">
        <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white p-4 shadow-sm">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-sk-text">Executive Summary</h3>
            <button
              type="button"
              onClick={handleCopySummary}
              disabled={isGenerating || !report.trim()}
              className="rounded-md border border-gray-200 dark:border-white/10 px-2.5 py-1 text-xs font-medium text-sk-text hover:bg-gray-100 dark:hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Copy summary
            </button>
          </div>
          <div className="text-sm text-sk-text leading-relaxed">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children }) => <h1 className="text-lg font-bold mt-3 mb-2">{children}</h1>,
                h2: ({ children }) => <h2 className="text-base font-bold mt-3 mb-1.5">{children}</h2>,
                h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>,
                p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                ul: ({ children }) => <ul className="list-disc pl-5 mb-2 space-y-0.5">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal pl-5 mb-2 space-y-0.5">{children}</ol>,
                li: ({ children }) => <li>{children}</li>,
                blockquote: ({ children }) => (
                  <blockquote className="border-l-3 border-gray-300 dark:border-white/20 pl-3 my-2 italic">
                    {children}
                  </blockquote>
                ),
                code: ({ children, className }) =>
                  className ? (
                    <code className={className}>{children}</code>
                  ) : (
                    <code className="px-1.5 py-0.5 rounded bg-black/10 dark:bg-white/10 font-mono text-xs">
                      {children}
                    </code>
                  ),
                pre: ({ children }) => (
                  <pre className="my-2 p-3 rounded-lg bg-gray-100 dark:bg-white/10 overflow-x-auto text-xs font-mono">
                    {children}
                  </pre>
                ),
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="text-sk-accent-red underline hover:opacity-80">
                    {children}
                  </a>
                ),
              }}
            >
              {report}
            </ReactMarkdown>
          </div>
        </div>
        <div>
          <label
            htmlFor="report-requirements"
            className="block text-xs font-medium text-sk-text mb-1"
          >
            Modification requirements (optional)
          </label>
          <textarea
            id="report-requirements"
            value={requirements}
            onChange={(e) => setRequirements(e.target.value)}
            placeholder="e.g. Focus on Q4 metrics, emphasise risks"
            className="w-full rounded-lg border border-gray-200 dark:border-white/10 bg-sk-white px-3 py-2 text-sm text-sk-text placeholder:text-sk-contrast-grey focus:outline-none focus:ring-2 focus:ring-sk-accent-red/50 min-h-[80px]"
            disabled={isGenerating}
          />
        </div>
        <button
          type="button"
          onClick={handleGenerateReport}
          disabled={isGenerating}
          className="w-full rounded-lg bg-sk-accent-red text-white text-sm font-medium py-2 px-3 hover:bg-sk-accent-red/90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Re-generate
        </button>
      </div>
    );
  }

  // 3d. No report yet (final answer state): Generate button only, no requirement text
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white p-4 shadow-sm">
        <h3 className="text-sm font-semibold text-sk-text mb-1">Executive Summary</h3>
        <p className="text-xs text-sk-contrast-grey leading-relaxed mb-4">
          Generate an executive summary for this session.
        </p>
        <button
          type="button"
          onClick={handleGenerateReport}
          disabled={isGenerating}
          className="w-full rounded-lg bg-sk-accent-red text-white text-sm font-medium py-2 px-3 hover:bg-sk-accent-red/90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Generate report
        </button>
      </div>
      {error && (
        <p className="text-xs text-amber-600 dark:text-amber-400">{error}</p>
      )}
    </div>
  );
}
