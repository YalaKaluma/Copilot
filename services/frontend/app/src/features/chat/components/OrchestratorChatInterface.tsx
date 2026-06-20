import React, { useState, useRef, useEffect } from "react";
import {
  Send,
  SquarePen,
  Paperclip,
  Check,
  Loader2,
  LayoutTemplate,
  X,
  Copy,
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import { cn } from "../../../shared/utils/cn";
import { apiClient } from "../../../shared/lib/api-client";
import { Message } from "../hooks/useLLM";
import { TemplateAutocomplete } from "./TemplateAutocomplete";
import type { TemplateAutocompleteHandle } from "./TemplateAutocomplete";
import { TemplateFormModal } from "./TemplateFormModal";
import type { FeedbackCategory } from "../services/feedbackService";
import { FeedbackButtons } from "./FeedbackButtons";
import { getAssistantMessageId } from "../utils/feedbackId";
import type {
  TemplateListItem,
  TemplateDetail,
  CreateTemplateRequest,
} from "../types/template.types";
import { getStageLoadingLabel } from "../utils/stage";

/** Renders message content with full markdown (headings, tables, lists, code blocks, etc.). */
function MessageContent({
  content,
  className,
}: {
  content: string;
  className?: string;
}) {
  if (!content.trim()) return null;
  return (
    <div className={cn("text-sm leading-relaxed break-words", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-lg font-bold mt-3 mb-2 text-sk-text">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-base font-bold mt-3 mb-1.5 text-sk-text">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-semibold mt-2 mb-1 text-sk-text">
              {children}
            </h3>
          ),
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold">{children}</strong>
          ),
          em: ({ children }) => (
            <em className="italic opacity-80">{children}</em>
          ),
          code: ({ children, className: codeClassName }) => {
            const isBlock = codeClassName?.includes("language-");
            if (isBlock) {
              return (
                <code className={cn("text-xs", codeClassName)}>{children}</code>
              );
            }
            return (
              <code className="px-1.5 py-0.5 rounded bg-black/10 dark:bg-white/10 font-mono text-xs">
                {children}
              </code>
            );
          },
          pre: ({ children }) => (
            <pre className="my-2 p-3 rounded-lg bg-gray-100 dark:bg-white/10 overflow-x-auto text-xs font-mono">
              {children}
            </pre>
          ),
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto">
              <table className="min-w-full text-xs border-collapse border border-gray-300 dark:border-white/10">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-gray-100 dark:bg-white/10">{children}</thead>
          ),
          th: ({ children }) => (
            <th className="px-3 py-1.5 text-left font-semibold border border-gray-300 dark:border-white/10 text-sk-text">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-1.5 border border-gray-300 dark:border-white/10">
              {children}
            </td>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-5 mb-2 space-y-0.5">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 mb-2 space-y-0.5">{children}</ol>
          ),
          li: ({ children }) => <li className="text-sm">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-3 border-gray-300 dark:border-white/20 pl-3 my-2 text-gray-600 dark:text-gray-300 italic">
              {children}
            </blockquote>
          ),
          hr: () => (
            <hr className="my-3 border-gray-300 dark:border-white/10" />
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sk-accent-red underline hover:opacity-80"
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

/** Animated three dots for loading state. */
function LoadingDots() {
  return (
    <span className="inline-flex gap-1 ml-0.5 align-middle" aria-hidden>
      <span
        className="w-1.5 h-1.5 rounded-full bg-current animate-[loading-dots_1.2s_ease-in-out_infinite]"
        style={{ animationDelay: "0ms" }}
      />
      <span
        className="w-1.5 h-1.5 rounded-full bg-current animate-[loading-dots_1.2s_ease-in-out_infinite]"
        style={{ animationDelay: "200ms" }}
      />
      <span
        className="w-1.5 h-1.5 rounded-full bg-current animate-[loading-dots_1.2s_ease-in-out_infinite]"
        style={{ animationDelay: "400ms" }}
      />
    </span>
  );
}

interface OrchestratorChatInterfaceProps {
  messages: Message[];
  isLoading: boolean;
  currentStage: string | null;
  sendMessage: (content: string) => Promise<unknown>;
  clearSession: () => Promise<void>;
  skaiConnected: boolean;
  /** When false, we're still checking SKAI auth status — don't show login panel until we know. */
  skaiStatusKnown?: boolean;
  onSkaiAuthChange: () => void;
  /** Called when the user sends a message (form submit or quick action). Use to e.g. switch right pane to Reasoning. */
  onUserMessageSent?: () => void;
  onUpdateMessageFeedback?: (
    assistantMessageId: string,
    feedback: { category: FeedbackCategory; reason?: string } | null,
  ) => void;
  onMarkActionSelected?: (messageId: string, action: string) => void;
  // Template props
  templates?: TemplateListItem[];
  activeTemplate?: TemplateDetail | null;
  onFetchTemplates?: () => Promise<void>;
  onSelectTemplate?: (id: string) => Promise<void>;
  onClearTemplate?: () => void;
  onCreateTemplate?: (data: CreateTemplateRequest) => Promise<TemplateDetail>;
  /** When true, show loading state in the main chat pane (e.g. URL hydration for an old chat). */
  isHydrating?: boolean;
  /** When true, user clicked a chat in history and we're loading it — show spinner until navigate. */
  loadingSelectingChat?: boolean;
}

export function OrchestratorChatInterface({
  messages,
  isLoading,
  currentStage,
  sendMessage,
  clearSession,
  skaiConnected,
  skaiStatusKnown = true,
  onSkaiAuthChange,
  onUserMessageSent,
  onUpdateMessageFeedback,
  onMarkActionSelected,
  templates = [],
  activeTemplate,
  onFetchTemplates,
  onSelectTemplate,
  onClearTemplate,
  onCreateTemplate,
  isHydrating = false,
  loadingSelectingChat = false,
}: OrchestratorChatInterfaceProps) {
  const [input, setInput] = useState("");
  const [templateFormOpen, setTemplateFormOpen] = useState(false);
  const [slashActive, setSlashActive] = useState(false);
  const [slashFilter, setSlashFilter] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const autocompleteRef = useRef<TemplateAutocompleteHandle>(null);

  // SKAI login form state
  const [skaiUsername, setSkaiUsername] = useState("");
  const [skaiPassword, setSkaiPassword] = useState("");
  const [skaiIsSubmitting, setSkaiIsSubmitting] = useState(false);
  const [skaiError, setSkaiError] = useState<string | null>(null);

  const handleSkaiLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setSkaiIsSubmitting(true);
    setSkaiError(null);
    try {
      await apiClient.post("/skai/auth/login", {
        username: skaiUsername,
        password: skaiPassword,
      });
      setSkaiPassword("");
      setSkaiUsername("");
      window.dispatchEvent(
        new CustomEvent("skai-auth-change", { detail: { connected: true } }),
      );
      onSkaiAuthChange();
    } catch (err) {
      setSkaiError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSkaiIsSubmitting(false);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (!input && inputRef.current) {
      inputRef.current.style.height = "2.5rem";
    }
  }, [input]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const message = input;
    setInput("");
    onUserMessageSent?.();
    await sendMessage(message);
  };

  const handleQuickAction = async (action: string, messageId?: string) => {
    if (!action.trim() || isLoading || !skaiConnected) return;
    if (messageId) onMarkActionSelected?.(messageId, action);
    setInput("");
    onUserMessageSent?.();
    await sendMessage(action);
  };

  const handleOtherOption = () => {
    inputRef.current?.focus();
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setInput(value);

    // Slash command detection
    if (value.startsWith("/")) {
      if (!slashActive) {
        onFetchTemplates?.();
      }
      setSlashActive(true);
      setSlashFilter(value.slice(1));
    } else {
      setSlashActive(false);
      setSlashFilter("");
    }
  };

  const handleTemplateSelect = async (id: string) => {
    setSlashActive(false);
    setSlashFilter("");
    setInput("");
    await onSelectTemplate?.(id);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Delegate to autocomplete when active
    if (slashActive && autocompleteRef.current) {
      const handled = autocompleteRef.current.handleKeyDown(e);
      if (handled) return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as React.FormEvent);
    }
  };

  const skaiLoginPanel = (
    <div className="rounded-xl border border-gray-200 dark:border-white/10 p-5 bg-sk-white">
      <form onSubmit={handleSkaiLogin} className="space-y-3">
        <div className="space-y-2">
          <label className="text-xs font-medium text-gray-600 dark:text-gray-300">
            Username
          </label>
          <input
            type="email"
            required
            value={skaiUsername}
            onChange={(e) => setSkaiUsername(e.target.value)}
            className="w-full rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white px-3 py-1.5 text-sm text-sk-text outline-none transition placeholder-gray-400 focus:border-sk-accent-red focus:ring-1 focus:ring-sk-accent-red/30"
            placeholder="you@company.com"
          />
        </div>
        <div className="space-y-2">
          <label className="text-xs font-medium text-gray-600 dark:text-gray-300">
            Password
          </label>
          <input
            type="password"
            required
            value={skaiPassword}
            onChange={(e) => setSkaiPassword(e.target.value)}
            className="w-full rounded-xl border border-gray-200 dark:border-white/10 bg-sk-white px-3 py-1.5 text-sm text-sk-text outline-none transition placeholder-gray-400 focus:border-sk-accent-red focus:ring-1 focus:ring-sk-accent-red/30"
            placeholder="password"
          />
        </div>

        <button
          type="submit"
          disabled={skaiIsSubmitting}
          className="w-full rounded-xl bg-sk-accent-red px-4 py-1.5 text-sm font-semibold text-white transition hover:bg-sk-accent-red/90 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"
        >
          {skaiIsSubmitting ? "Connecting..." : "Connect to SKAI"}
        </button>
      </form>

      {skaiError && (
        <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-600">
          {skaiError}
        </p>
      )}
    </div>
  );

  return (
    <div
      id="orchestrator-chat"
      className="flex flex-col h-full bg-transparent text-sk-text"
    >
      {/* Messages */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="px-3 sm:px-4 py-4">
          {/* Only show SKAI login panel after we've checked status; on refresh we don't pop it up until we know user is disconnected. */}
          {skaiStatusKnown && !skaiConnected ? (
            <div
              className={cn(
                "w-full max-w-xs",
                messages.length === 0 ? "mx-auto mt-16" : "mb-4",
              )}
            >
              {skaiLoginPanel}
            </div>
          ) : null}

          {/* Spinner when: (1) user clicked an old chat — always show until loaded; (2) loading by URL and no messages yet. Never show when only chat history list is syncing. */}
          {loadingSelectingChat || (isHydrating && messages.length === 0) ? (
            <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-center">
              <Loader2 className="w-8 h-8 text-sk-contrast-grey animate-spin mb-3" />
              <p className="text-sm text-sk-contrast-grey">
                Loading conversation...
              </p>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-center">
              {skaiConnected ? (
                <>
                  <h3 className="text-2xl font-semibold text-sk-text mb-2">
                    Ask SKAI anything
                  </h3>
                  <p className="text-sm text-sk-contrast-grey max-w-sm">
                    Start a conversation about pricing, promotions, and retailer
                    performance.
                  </p>
                </>
              ) : null}
            </div>
          ) : (
            <div className="space-y-4">
              <AnimatePresence initial={false}>
                {messages.map((message) => (
                  <motion.div
                    key={message.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.2 }}
                    className="space-y-1.5"
                  >
                    {/* Message bubble (show empty assistant when loading = stage placeholder) */}
                    {!(
                      message.role === "assistant" &&
                      !message.content &&
                      !isLoading
                    ) && (
                      <div
                        className={cn(
                          "flex",
                          message.role === "user"
                            ? "justify-end"
                            : "justify-start",
                        )}
                      >
                        <div
                          className={cn(
                            "px-3 sm:px-3.5 py-2 sm:py-2.5 rounded-2xl border",
                            message.role === "user"
                              ? "max-w-[85%] sm:max-w-[80%] bg-sk-light-grey border-gray-200 dark:border-white/10 text-sk-text"
                              : message.role === "assistant" &&
                                  !message.content &&
                                  isLoading
                                ? "w-fit bg-gray-200 dark:bg-white/10 border-gray-300 dark:border-white/10 text-sk-text"
                                : "w-full bg-gray-200 dark:bg-white/10 border-gray-300 dark:border-white/10 text-sk-text",
                          )}
                        >
                          {message.role === "assistant" &&
                          !message.content &&
                          isLoading ? (
                            <p className="text-sm text-gray-600 dark:text-gray-300 flex items-center">
                              {getStageLoadingLabel(currentStage)}
                              <LoadingDots />
                            </p>
                          ) : (
                            <MessageContent
                              content={message.content}
                              className="break-words"
                            />
                          )}
                          {message.role === "assistant" &&
                            message.actions &&
                            message.actions.length > 0 && (
                              <div className="mt-2 flex flex-col gap-1.5">
                                {message.actions.map((action) => {
                                  const isSelected = message.selectedAction === action;
                                  const hasSelection = !!message.selectedAction;
                                  if (hasSelection && !isSelected) return null;
                                  return (
                                    <button
                                      key={action}
                                      type="button"
                                      onClick={() => handleQuickAction(action, message.id)}
                                      disabled={hasSelection || isLoading || !skaiConnected}
                                      className={cn(
                                        "w-full px-3 py-2 rounded-xl text-xs font-medium text-left transition-colors",
                                        isSelected
                                          ? "bg-sk-accent-red/10 border border-sk-accent-red/30 text-sk-accent-red"
                                          : "bg-sk-white border border-gray-300 dark:border-white/10 text-sk-text hover:bg-gray-50 dark:hover:bg-white/5 cursor-pointer",
                                        (hasSelection || isLoading || !skaiConnected) && !isSelected
                                          ? "opacity-60 cursor-not-allowed"
                                          : "",
                                      )}
                                    >
                                      {isSelected && (
                                        <Check className="w-3 h-3 inline mr-1.5 -mt-0.5" />
                                      )}
                                      {action}
                                    </button>
                                  );
                                })}
                                {message.allowOther !== false && !message.selectedAction && (
                                  <button
                                    type="button"
                                    onClick={handleOtherOption}
                                    disabled={isLoading || !skaiConnected}
                                    className="w-full px-3 py-2 rounded-xl text-xs font-medium bg-transparent border border-dashed border-gray-300 dark:border-white/20 text-gray-600 dark:text-gray-300 text-left hover:text-sk-text hover:border-gray-400 dark:hover:border-white/30 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
                                  >
                                    Other response
                                  </button>
                                )}
                              </div>
                            )}
                          {!(
                            message.role === "assistant" &&
                            !message.content &&
                            isLoading
                          ) && (
                            <div
                              className={cn(
                                "flex items-center gap-2 mt-1",
                                message.role === "assistant" && message.content
                                  ? "justify-between"
                                  : "",
                              )}
                            >
                              <p
                                className={cn(
                                  "text-[10px]",
                                  message.role === "user"
                                    ? "text-gray-400"
                                    : "text-gray-500",
                                )}
                              >
                                {message.timestamp.toLocaleTimeString([], {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </p>
                              {message.role === "assistant" &&
                                message.content &&
                                message.content.trim() !== "" && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      navigator.clipboard
                                        .writeText(message.content)
                                        .then(() => {
                                          toast.success("Copied to clipboard");
                                        })
                                        .catch(() => {
                                          toast.error("Failed to copy response");
                                        });
                                    }}
                                    className="p-1 rounded text-gray-500 hover:text-sk-text hover:bg-gray-300/50 dark:hover:bg-white/10 transition-colors"
                                    title="Copy"
                                    aria-label="Copy response"
                                  >
                                    <Copy className="w-3.5 h-3.5" />
                                  </button>
                                )}
                            </div>
                          )}
                          {!(
                            message.role === "assistant" &&
                            !message.content &&
                            isLoading
                          ) &&
                            message.role === "assistant" &&
                            getAssistantMessageId(message) && (
                              <FeedbackButtons
                                assistantMessageId={
                                  getAssistantMessageId(message)!
                                }
                                initialSubmitted={
                                  message.feedback?.category ?? null
                                }
                                onSubmitted={(category, reason) =>
                                  onUpdateMessageFeedback?.(
                                    getAssistantMessageId(message)!,
                                    {
                                      category,
                                      reason,
                                    },
                                  )
                                }
                                onUpdated={(category, reason) =>
                                  onUpdateMessageFeedback?.(
                                    getAssistantMessageId(message)!,
                                    {
                                      category,
                                      reason,
                                    },
                                  )
                                }
                                onRemoved={() =>
                                  onUpdateMessageFeedback?.(
                                    getAssistantMessageId(message)!,
                                    null,
                                  )
                                }
                              />
                            )}
                        </div>
                      </div>
                    )}
                  </motion.div>
                ))}
              </AnimatePresence>
              {/* Stage placeholder when waiting for assistant (user just sent, no assistant message yet) */}
              {isLoading &&
                messages.length > 0 &&
                messages[messages.length - 1].role === "user" && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                    className="flex justify-start"
                  >
                    <div className="w-fit px-3 sm:px-3.5 py-2 sm:py-2.5 rounded-2xl border bg-gray-200 dark:bg-white/10 border-gray-300 dark:border-white/10 text-sk-text">
                      <p className="text-sm text-gray-600 dark:text-gray-300 flex items-center">
                        {getStageLoadingLabel(currentStage)}
                        <LoadingDots />
                      </p>
                    </div>
                  </motion.div>
                )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Example questions */}
      {skaiConnected && messages.length === 0 && (
        <div className="flex-shrink-0 px-3 sm:px-4 pb-2 space-y-1.5 flex flex-col items-center">
          <div className="w-full max-w-[630px] space-y-1.5">
            {[
              "Tell me what questions I can ask?",
              "Which tactics have the best ROI for my product?",
              "What happens to the volume and margin if we take +3% price on SKU1?",
            ].map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => setInput(q)}
                className="flex items-center gap-2 text-sm text-gray-400 hover:text-sk-text transition-colors text-left cursor-pointer"
              >
                <span className="text-gray-300">&gt;</span>
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="flex-shrink-0 px-3 sm:px-4 py-3 border-t border-gray-200 dark:border-white/10 bg-gray-50/50 dark:bg-transparent flex flex-col items-center"
      >
        {/* Active template chip */}
        {activeTemplate && (
          <div className="flex items-center gap-1.5 mb-2 w-full max-w-[630px]">
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium text-sk-accent-red bg-sk-accent-red/10">
              <LayoutTemplate className="w-3 h-3" />
              {activeTemplate.name}
              <button
                type="button"
                onClick={onClearTemplate}
                className="ml-0.5 p-0.5 rounded-full hover:bg-sk-accent-red/20 transition-colors cursor-pointer"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          </div>
        )}

        <div className="relative flex items-end gap-2 p-2 rounded-2xl bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 shadow-sm focus-within:border-sk-accent-red/50 focus-within:ring-2 focus-within:ring-sk-accent-red/10 transition-all w-full max-w-[630px]">
          {/* Slash command autocomplete */}
          <AnimatePresence>
            {slashActive && (
              <TemplateAutocomplete
                ref={autocompleteRef}
                templates={templates}
                filter={slashFilter}
                onSelect={handleTemplateSelect}
                onClose={() => {
                  setSlashActive(false);
                  setSlashFilter("");
                  setInput("");
                }}
                onCreate={() => {
                  setSlashActive(false);
                  setSlashFilter("");
                  setInput("");
                  setTemplateFormOpen(true);
                }}
              />
            )}
          </AnimatePresence>

          <textarea
            ref={inputRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={
              activeTemplate
                ? `Ask anything (using ${activeTemplate.name})`
                : "Ask anything"
            }
            disabled={!skaiConnected}
            rows={1}
            className="flex-1 min-h-[2.5rem] px-2 py-2.5 bg-transparent border-none resize-none focus:outline-none focus:ring-0 text-sm placeholder-gray-400 dark:placeholder-gray-500 leading-5 text-sk-text"
            style={{
              overflow: input && input.length > 100 ? "auto" : "hidden",
              height: "2.5rem",
            }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = "2.5rem";
              const scrollHeight = target.scrollHeight;
              const maxHeight = 128;
              const newHeight = Math.min(scrollHeight, maxHeight);
              target.style.height = `${newHeight}px`;
              target.style.overflow =
                newHeight >= maxHeight ? "auto" : "hidden";
            }}
          />
          {messages.length > 0 && (
            <div className="relative group flex-shrink-0">
              <button
                type="button"
                onClick={clearSession}
                className="h-10 w-10 rounded-full transition-all flex items-center justify-center text-gray-400 hover:text-sk-text hover:bg-gray-200 dark:hover:bg-white/10 cursor-pointer"
              >
                <SquarePen className="w-4 h-4" />
              </button>
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity">
                <div className="px-2.5 py-1 rounded-lg bg-gray-800 text-white text-xs whitespace-nowrap">
                  Create new chat
                </div>
                <div className="flex justify-center">
                  <div className="w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-t-[5px] border-t-gray-800" />
                </div>
              </div>
            </div>
          )}
          <button
            type="button"
            className="h-10 w-10 rounded-full transition-all flex-shrink-0 flex items-center justify-center text-gray-400 hover:text-sk-text hover:bg-gray-200 dark:hover:bg-white/10 cursor-pointer"
            aria-label="Attach file"
          >
            <Paperclip className="w-4 h-4" />
          </button>
          <button
            type="submit"
            disabled={!input.trim() || isLoading || !skaiConnected}
            className={cn(
              "h-10 w-10 rounded-full transition-all flex-shrink-0 flex items-center justify-center border",
              !input.trim() || isLoading || !skaiConnected
                ? "bg-gray-200 dark:bg-white/10 text-gray-400 border-gray-200 dark:border-white/10 cursor-not-allowed"
                : "bg-sk-accent-red text-white border-sk-accent-red hover:bg-sk-accent-red/90 cursor-pointer",
            )}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>

      {/* Template create modal (from slash command) */}
      <AnimatePresence>
        {templateFormOpen && onCreateTemplate && (
          <TemplateFormModal
            onSave={async (data) => {
              await onCreateTemplate(data as CreateTemplateRequest);
              setTemplateFormOpen(false);
            }}
            onClose={() => setTemplateFormOpen(false)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
