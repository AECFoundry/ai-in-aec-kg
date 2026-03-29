import { motion } from "framer-motion";
import { useVoice } from "../hooks/useVoice";

const stateColors = {
  idle: {
    bg: "rgba(99, 102, 241, 0.15)",
    ring: "rgba(99, 102, 241, 0.3)",
    glow: "rgba(99, 102, 241, 0.2)",
    text: "text-indigo-300",
  },
  listening: {
    bg: "rgba(244, 63, 94, 0.2)",
    ring: "rgba(244, 63, 94, 0.4)",
    glow: "rgba(244, 63, 94, 0.3)",
    text: "text-rose-400",
  },
  processing: {
    bg: "rgba(99, 102, 241, 0.15)",
    ring: "rgba(99, 102, 241, 0.3)",
    glow: "rgba(99, 102, 241, 0.15)",
    text: "text-indigo-300",
  },
  speaking: {
    bg: "rgba(20, 184, 166, 0.2)",
    ring: "rgba(20, 184, 166, 0.4)",
    glow: "rgba(20, 184, 166, 0.3)",
    text: "text-teal-400",
  },
};

function MicIcon() {
  return (
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
      <rect x="9" y="1" width="6" height="12" rx="3" />
      <path d="M5 10a7 7 0 0 0 14 0" />
      <line x1="12" y1="17" x2="12" y2="21" />
      <line x1="8" y1="21" x2="16" y2="21" />
    </svg>
  );
}

function WaveformBars() {
  return (
    <div className="flex items-center gap-[2px] h-[18px]">
      {[0, 1, 2, 3, 4].map((i) => (
        <motion.div
          key={i}
          className="w-[2px] rounded-full bg-teal-400"
          animate={{ height: ["6px", "16px", "6px"] }}
          transition={{
            duration: 0.8,
            repeat: Infinity,
            delay: i * 0.12,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}

function ProcessingSpinner() {
  return (
    <motion.div
      className="w-[18px] h-[18px] rounded-full border-2 border-indigo-400/30 border-t-indigo-400"
      animate={{ rotate: 360 }}
      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
    />
  );
}

export default function VoiceOrb() {
  const { voiceState, toggle, isSupported } = useVoice();

  if (!isSupported) return null;

  const colors = stateColors[voiceState];

  return (
    <motion.button
      type="button"
      onClick={toggle}
      className={`
        relative w-11 h-11 shrink-0 rounded-full
        backdrop-blur-xl border
        transition-colors duration-300
        flex items-center justify-center
        ${colors.text}
      `}
      style={{
        backgroundColor: colors.bg,
        borderColor: colors.ring,
        boxShadow:
          voiceState !== "idle"
            ? `0 0 20px ${colors.glow}, 0 0 40px ${colors.glow}`
            : "none",
      }}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
    >
      {voiceState === "speaking" ? (
        <WaveformBars />
      ) : voiceState === "processing" ? (
        <ProcessingSpinner />
      ) : voiceState === "listening" ? (
        <>
          <motion.div
            className="absolute inset-0 rounded-full border"
            style={{ borderColor: colors.ring }}
            animate={{ scale: [1, 1.4], opacity: [0.5, 0] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut" }}
          />
          <MicIcon />
        </>
      ) : (
        <MicIcon />
      )}
    </motion.button>
  );
}
