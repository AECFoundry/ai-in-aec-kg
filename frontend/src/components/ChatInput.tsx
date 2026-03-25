import { useState, useCallback } from "react";
import type { FormEvent, KeyboardEvent } from "react";

interface ChatInputProps {
  onSubmit: (text: string) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
}

export default function ChatInput({
  onSubmit,
  placeholder = "Ask about the conference...",
  className = "",
  disabled = false,
}: ChatInputProps) {
  const [value, setValue] = useState("");

  const handleSubmit = useCallback(
    (e?: FormEvent) => {
      e?.preventDefault();
      const trimmed = value.trim();
      if (!trimmed || disabled) return;
      onSubmit(trimmed);
      setValue("");
    },
    [value, onSubmit, disabled]
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  return (
    <form onSubmit={handleSubmit} className={`flex gap-2 ${className}`}>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        className="
          flex-1 px-5 py-3.5 rounded-2xl
          bg-white/[0.04] backdrop-blur-xl
          border border-white/[0.08]
          text-slate-200 placeholder-slate-500
          text-sm tracking-wide
          outline-none
          focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/25
          transition-all duration-300
          disabled:opacity-50
        "
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className="
          px-5 py-3.5 rounded-2xl
          bg-indigo-600/80 hover:bg-indigo-500/80
          backdrop-blur-xl
          border border-indigo-400/20
          text-white text-sm font-medium tracking-wide
          transition-all duration-300
          disabled:opacity-30 disabled:cursor-not-allowed
          hover:shadow-lg hover:shadow-indigo-500/20
          active:scale-[0.97]
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
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      </button>
    </form>
  );
}
