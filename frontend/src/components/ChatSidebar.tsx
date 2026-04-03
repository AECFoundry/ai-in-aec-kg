import React, { useRef, useEffect, useMemo, useState, type ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import { useAppStore } from "../stores/appStore";
import { useChat } from "../hooks/useChat";
import { nodeColors } from "../styles/theme";
import ChatInput from "./ChatInput";
import type { ChatMessage, SourceRef, AgentTraceStep } from "../lib/types";

const PROSE_CLASSES =
  "max-w-none " +
  "[&_p]:my-1.5 [&_ul]:my-1.5 [&_ol]:my-1.5 [&_li]:my-0.5 " +
  "[&_h3]:text-sm [&_h3]:font-semibold [&_h3]:text-body [&_h3]:mt-3 [&_h3]:mb-1 " +
  "[&_h4]:text-xs [&_h4]:font-semibold [&_h4]:text-secondary [&_h4]:mt-2 [&_h4]:mb-1 " +
  "[&_strong]:text-heading [&_em]:text-secondary " +
  "[&_code]:text-indigo-300 [&_code]:bg-surface [&_code]:px-1 [&_code]:rounded " +
  "[&_pre]:bg-surface [&_pre]:rounded-lg [&_pre]:p-3 " +
  "[&_a]:text-indigo-400 [&_blockquote]:border-indigo-500/30 [&_blockquote]:text-tertiary " +
  "[&_hr]:border-edge";

const CITE_RE = /\[(\d+)\]/g;

/** Turn a string into an array of text fragments and citation buttons. */
function injectCitations(
  text: string,
  citeMap: Map<number, SourceRef>,
  onCiteClick: (id: string) => void,
  keyPrefix: string,
): ReactNode[] {
  const parts: ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  CITE_RE.lastIndex = 0;
  while ((match = CITE_RE.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const n = parseInt(match[1]);
    const source = citeMap.get(n);
    if (source) {
      const color = nodeColors[source.label] ?? "#6366f1";
      parts.push(
        <button
          key={`${keyPrefix}-${match.index}`}
          onClick={() => onCiteClick(source.id)}
          className="inline-flex items-center gap-0.5 px-1.5 py-0.5 mx-0.5 rounded text-[11px] font-medium align-baseline transition-all duration-150 hover:brightness-125 cursor-pointer"
          style={{
            backgroundColor: `${color}20`,
            color: color,
            border: `1px solid ${color}30`,
          }}
          title={`${source.name} (${source.label})`}
        >
          {n}
        </button>,
      );
    } else {
      parts.push(match[0]);
    }
    last = CITE_RE.lastIndex;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

/** Process React children, replacing string [N] text with citation buttons. */
function processChildren(
  children: ReactNode,
  citeMap: Map<number, SourceRef>,
  onCiteClick: (id: string) => void,
  keyPrefix: string,
): ReactNode {
  return React.Children.map(children, (child, i) => {
    if (typeof child === "string") {
      const parts = injectCitations(child, citeMap, onCiteClick, `${keyPrefix}-${i}`);
      return parts.length === 1 ? parts[0] : <>{parts}</>;
    }
    return child;
  });
}

/**
 * Renders markdown with clickable citation buttons for [N] markers.
 * Uses ReactMarkdown's `components` prop to inject buttons into rendered
 * HTML elements — never modifies ReactMarkdown's string input.
 */
function CitedMarkdown({
  content,
  sources,
  onCiteClick,
}: {
  content: string;
  sources: SourceRef[];
  onCiteClick: (sourceId: string) => void;
}) {
  const citeMap = useMemo(() => {
    const map = new Map<number, SourceRef>();
    for (const s of sources) {
      if (s.citation) map.set(s.citation, s);
    }
    return map;
  }, [sources]);

  const components = useMemo(() => {
    // Build custom renderers for text-containing elements
    const wrap = (Tag: string) =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ({ children, node, ...rest }: any) =>
        React.createElement(Tag, rest, processChildren(children, citeMap, onCiteClick, Tag));
    return {
      p: wrap("p"),
      li: wrap("li"),
      td: wrap("td"),
      h1: wrap("h1"),
      h2: wrap("h2"),
      h3: wrap("h3"),
      h4: wrap("h4"),
      strong: wrap("strong"),
      em: wrap("em"),
    };
  }, [citeMap, onCiteClick]);

  return (
    <div className={PROSE_CLASSES}>
      <ReactMarkdown components={components}>{content}</ReactMarkdown>
    </div>
  );
}

const traceIcons: Record<AgentTraceStep["type"], ReactNode> = {
  thinking: (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4" />
      <path d="M12 8h.01" />
    </svg>
  ),
  tool_call: (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  ),
  tool_progress: (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  ),
  tool_result: (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
};

function AgentTrace({ steps, isStreaming }: { steps: AgentTraceStep[]; isStreaming?: boolean }) {
  const [expanded, setExpanded] = useState(false);

  if (steps.length === 0) return null;

  return (
    <div className={`mb-2 rounded-lg px-2.5 py-1.5 -mx-1 ${isStreaming ? "animate-breathe-glow" : ""}`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className={`flex items-center gap-1.5 text-[10px] hover:text-secondary transition-colors uppercase tracking-wider font-medium ${
          isStreaming ? "text-indigo-400" : "text-tertiary"
        }`}
      >
        <motion.svg
          width="10"
          height="10"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          animate={{ rotate: expanded ? 90 : 0 }}
          transition={{ duration: 0.15 }}
        >
          <polyline points="9 18 15 12 9 6" />
        </motion.svg>
        {isStreaming ? "Reasoning..." : `${steps.length} steps`}
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-1.5 ml-1 border-l border-edge pl-3 space-y-1">
              {steps.map((step, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -4 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.15, delay: isStreaming ? 0.05 : 0 }}
                  className="flex items-start gap-2 text-[11px] text-tertiary"
                >
                  <span className={`mt-0.5 shrink-0 ${
                    step.type === "tool_result"
                      ? "text-emerald-500/70"
                      : step.type === "tool_call"
                        ? "text-indigo-400/70"
                        : "text-tertiary/70"
                  }`}>
                    {traceIcons[step.type]}
                  </span>
                  <span className="leading-tight">{step.detail}</span>
                </motion.div>
              ))}
              {isStreaming && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center gap-1.5 text-[11px] text-tertiary"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400/50 animate-pulse" />
                </motion.div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const focusNode = useAppStore((s) => s.focusNode);
  const graphData = useAppStore((s) => s.graphData);
  const setSelectedNode = useAppStore((s) => s.setSelectedNode);
  const highlightedNodes = useAppStore((s) => s.highlightedNodes);
  const clearHighlight = useAppStore((s) => s.clearHighlight);

  const handleSourceClick = (sourceId: string) => {
    if (highlightedNodes.size === 1 && highlightedNodes.has(sourceId)) {
      clearHighlight();
    } else {
      focusNode(sourceId);
      // Open card after camera arrives
      const targetNode = graphData?.nodes.find((n: { id: string }) => n.id === sourceId);
      if (targetNode) {
        setTimeout(() => setSelectedNode(targetNode), 1500);
      }
    }
  };

  const sources = message.sources ?? [];

  // Hide empty streaming bubble before first SSE event arrives
  if (message.isStreaming && !message.content && (!message.agentTrace || message.agentTrace.length === 0)) {
    return (
      <div className="flex justify-start mb-4">
        <div className="bg-surface border border-edge rounded-2xl rounded-bl-md px-5 py-4">
          <div className="flex gap-1.5">
            <span className="w-2 h-2 bg-indigo-400/60 rounded-full animate-bounce [animation-delay:0ms]" />
            <span className="w-2 h-2 bg-indigo-400/60 rounded-full animate-bounce [animation-delay:150ms]" />
            <span className="w-2 h-2 bg-indigo-400/60 rounded-full animate-bounce [animation-delay:300ms]" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`
          rounded-2xl px-4 py-3 text-sm leading-relaxed
          ${
            isUser
              ? "max-w-[85%] bg-indigo-600/60 text-white rounded-br-md"
              : "w-full bg-surface border border-edge text-body rounded-bl-md"
          }
        `}
      >
        {/* Agent reasoning trace (above assistant content) */}
        {!isUser && message.agentTrace && message.agentTrace.length > 0 && (
          <AgentTrace steps={message.agentTrace} isStreaming={message.isStreaming} />
        )}

        {isUser ? (
          <p>{message.content}</p>
        ) : message.isStreaming && !message.content ? (
          null
        ) : sources.length > 0 ? (
          <CitedMarkdown
            content={message.content}
            sources={sources}
            onCiteClick={handleSourceClick}
          />
        ) : (
          <div className={PROSE_CLASSES}>
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {/* Sources footnote list */}
        {sources.length > 0 && (
          <div className="mt-3 pt-2 border-t border-edge space-y-1">
            {sources.map((source, i) => {
              const color = nodeColors[source.label] ?? "#6366f1";
              return (
                <button
                  key={i}
                  onClick={() => handleSourceClick(source.id)}
                  className="flex items-center gap-2 w-full text-left px-2 py-1 rounded-lg hover:bg-surface transition-colors duration-150 group"
                >
                  <span
                    className="shrink-0 w-5 h-5 flex items-center justify-center rounded text-[10px] font-semibold"
                    style={{
                      backgroundColor: `${color}20`,
                      color: color,
                    }}
                  >
                    {source.citation ?? i + 1}
                  </span>
                  <span className="text-[12px] text-tertiary group-hover:text-body truncate transition-colors">
                    {source.name}
                  </span>
                  <span className="ml-auto text-[10px] text-tertiary uppercase tracking-wider shrink-0">
                    {source.label}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ChatSidebar() {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const messages = useAppStore((s) => s.messages);
  const isLoading = useAppStore((s) => s.isLoading);
  const setMessages = useAppStore((s) => s.setMessages);
  const setSidebarOpen = useAppStore((s) => s.setSidebarOpen);
  const clearHighlight = useAppStore((s) => s.clearHighlight);
  const { sendMessage } = useChat();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleClose = () => {
    setSidebarOpen(false);
    clearHighlight();
  };

  const handleClearChat = () => {
    setMessages([]);
    clearHighlight();
  };

  return (
    <AnimatePresence>
      {sidebarOpen && (
        <motion.aside
          initial={{ x: 420, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 420, opacity: 0 }}
          transition={{ type: "spring", damping: 30, stiffness: 300 }}
          className="
            fixed top-0 right-0 h-full w-[420px] z-40
            bg-panel backdrop-blur-2xl
            border-l border-edge
            flex flex-col
          "
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-5 border-b border-edge">
            <div>
              <h2 className="text-base font-semibold text-heading tracking-wide">
                AI in AEC Explorer
              </h2>
              <p className="text-[11px] text-tertiary mt-0.5 tracking-wider uppercase">
                Knowledge Graph Chat
              </p>
            </div>
            <div className="flex items-center gap-1">
              {messages.length > 0 && (
                <button
                  onClick={handleClearChat}
                  title="Clear chat"
                  className="
                    p-2 rounded-xl
                    hover:bg-surface-hover
                    text-tertiary hover:text-body
                    transition-all duration-200
                  "
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M12 20h9" />
                    <path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4Z" />
                  </svg>
                </button>
              )}
              <button
                onClick={handleClose}
                className="
                  p-2 rounded-xl
                  hover:bg-surface-hover
                  text-tertiary hover:text-heading
                  transition-all duration-200
                "
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-5 py-4">
            {messages.length === 0 && !isLoading && (
              <div className="flex flex-col items-center justify-center h-full text-center opacity-40">
                <svg
                  width="48"
                  height="48"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="text-tertiary mb-4"
                >
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                <p className="text-sm text-tertiary">
                  Ask a question to explore
                  <br />
                  the knowledge graph
                </p>
              </div>
            )}

            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="px-5 py-4 border-t border-edge">
            <ChatInput
              onSubmit={sendMessage}
              disabled={isLoading}
              placeholder="Ask a follow-up..."
            />
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
