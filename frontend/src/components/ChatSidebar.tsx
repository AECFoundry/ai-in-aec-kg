import { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import { useAppStore } from "../stores/appStore";
import { useChat } from "../hooks/useChat";
import ChatInput from "./ChatInput";
import type { ChatMessage } from "../lib/types";

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`
          max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed
          ${
            isUser
              ? "bg-indigo-600/60 text-white rounded-br-md"
              : "bg-white/[0.04] border border-white/[0.06] text-slate-200 rounded-bl-md"
          }
        `}
      >
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none [&_p]:my-1.5 [&_ul]:my-1.5 [&_ol]:my-1.5 [&_li]:my-0.5 [&_code]:text-indigo-300 [&_code]:bg-white/5 [&_code]:px-1 [&_code]:rounded [&_pre]:bg-white/5 [&_pre]:rounded-lg [&_pre]:p-3 [&_a]:text-indigo-400">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {/* Sources */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-2 border-t border-white/[0.06] flex flex-wrap gap-1.5">
            {message.sources.map((source, i) => (
              <span
                key={i}
                className="inline-block px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-300/80 text-[11px] tracking-wide"
                title={`${source.label} — relevance: ${(source.score * 100).toFixed(0)}%`}
              >
                {source.name}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function LoadingIndicator() {
  return (
    <div className="flex justify-start mb-4">
      <div className="bg-white/[0.04] border border-white/[0.06] rounded-2xl rounded-bl-md px-5 py-4">
        <div className="flex gap-1.5">
          <span className="w-2 h-2 bg-indigo-400/60 rounded-full animate-bounce [animation-delay:0ms]" />
          <span className="w-2 h-2 bg-indigo-400/60 rounded-full animate-bounce [animation-delay:150ms]" />
          <span className="w-2 h-2 bg-indigo-400/60 rounded-full animate-bounce [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  );
}

export default function ChatSidebar() {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const messages = useAppStore((s) => s.messages);
  const isLoading = useAppStore((s) => s.isLoading);
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
            bg-[#000011]/80 backdrop-blur-2xl
            border-l border-white/[0.06]
            flex flex-col
          "
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-5 border-b border-white/[0.06]">
            <div>
              <h2 className="text-base font-semibold text-white tracking-wide">
                AI in AEC Explorer
              </h2>
              <p className="text-[11px] text-slate-500 mt-0.5 tracking-wider uppercase">
                Knowledge Graph Chat
              </p>
            </div>
            <button
              onClick={handleClose}
              className="
                p-2 rounded-xl
                hover:bg-white/[0.06]
                text-slate-400 hover:text-white
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
                  className="text-slate-500 mb-4"
                >
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                <p className="text-sm text-slate-500">
                  Ask a question to explore
                  <br />
                  the knowledge graph
                </p>
              </div>
            )}

            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}

            {isLoading && <LoadingIndicator />}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="px-5 py-4 border-t border-white/[0.06]">
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
