import { useState, useCallback } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import VoiceOrb from "./VoiceOrb";

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
    <form onSubmit={handleSubmit} className={`flex items-center gap-2 ${className}`}>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        className="
          flex-1 px-5 py-3.5 rounded-2xl
          bg-surface backdrop-blur-xl
          border border-edge-mid
          text-body placeholder-ghost
          text-sm tracking-wide
          outline-none
          focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/25
          focus:bg-surface-hover
          transition-all duration-300
          disabled:opacity-50
        "
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className="
          w-11 h-11 shrink-0 rounded-full
          flex items-center justify-center
          bg-indigo-600/80 hover:bg-indigo-500/80
          backdrop-blur-xl
          border border-indigo-400/20
          text-white
          transition-all duration-300
          disabled:opacity-30 disabled:cursor-not-allowed
          hover:shadow-lg hover:shadow-indigo-500/20
          active:scale-[0.95]
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
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      </button>
      <VoiceOrb />
    </form>
  );
}
