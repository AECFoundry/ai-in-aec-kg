import { motion, AnimatePresence } from "framer-motion";
import { useVoice } from "../hooks/useVoice";
import { useAppStore } from "../stores/appStore";

const stateColors = {
  idle: {
    bg: "rgba(99, 102, 241, 0.15)",
    ring: "rgba(99, 102, 241, 0.3)",
    glow: "rgba(99, 102, 241, 0.2)",
  },
  listening: {
    bg: "rgba(244, 63, 94, 0.2)",
    ring: "rgba(244, 63, 94, 0.4)",
    glow: "rgba(244, 63, 94, 0.3)",
  },
  processing: {
    bg: "rgba(99, 102, 241, 0.15)",
    ring: "rgba(99, 102, 241, 0.3)",
    glow: "rgba(99, 102, 241, 0.15)",
  },
  speaking: {
    bg: "rgba(20, 184, 166, 0.2)",
    ring: "rgba(20, 184, 166, 0.4)",
    glow: "rgba(20, 184, 166, 0.3)",
  },
};

function MicIcon() {
  return (
    <svg
      width="22"
      height="22"
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
    <div className="flex items-center gap-[3px] h-5">
      {[0, 1, 2, 3, 4].map((i) => (
        <motion.div
          key={i}
          className="w-[3px] rounded-full bg-teal-400"
          animate={{ height: ["8px", "20px", "8px"] }}
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
      className="w-5 h-5 rounded-full border-2 border-indigo-400/30 border-t-indigo-400"
      animate={{ rotate: 360 }}
      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
    />
  );
}

export default function VoiceOrb() {
  const { voiceState, toggle, isSupported } = useVoice();
  const graphData = useAppStore((s) => s.graphData);
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);

  if (!isSupported || !graphData) return null;

  const colors = stateColors[voiceState];
  const isActive = voiceState !== "idle";

  return (
    <div
      className={`fixed z-30 ${sidebarOpen ? "bottom-8" : "bottom-28"}`}
      style={{
        left: "320px",
        width: sidebarOpen ? "calc(100% - 320px - 420px)" : "calc(100% - 320px)",
      }}
    >
      <div className="flex justify-center">
        <div className="relative">
          <AnimatePresence>
            {isActive && (
              <motion.div
                className="absolute inset-0 rounded-full"
                initial={{ scale: 1, opacity: 0 }}
                animate={{ scale: 2.5, opacity: 0 }}
                exit={{ scale: 1, opacity: 0 }}
                transition={{ duration: 2, repeat: Infinity, ease: "easeOut" }}
                style={{ backgroundColor: colors.glow }}
              />
            )}
          </AnimatePresence>

          <AnimatePresence>
            {voiceState === "listening" && (
              <>
                {[0, 1, 2].map((i) => (
                  <motion.div
                    key={i}
                    className="absolute inset-0 rounded-full border"
                    style={{ borderColor: colors.ring }}
                    initial={{ scale: 1, opacity: 0.6 }}
                    animate={{ scale: 3, opacity: 0 }}
                    transition={{
                      duration: 2,
                      repeat: Infinity,
                      delay: i * 0.6,
                      ease: "easeOut",
                    }}
                  />
                ))}
              </>
            )}
          </AnimatePresence>

          <motion.button
            onClick={toggle}
            className="relative w-14 h-14 rounded-full flex items-center justify-center backdrop-blur-xl border transition-colors duration-300"
            style={{
              backgroundColor: colors.bg,
              borderColor: colors.ring,
              boxShadow: `0 0 30px ${colors.glow}, 0 0 60px ${colors.glow}`,
            }}
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.95 }}
            animate={voiceState === "idle" ? { scale: [1, 1.04, 1] } : {}}
            transition={
              voiceState === "idle"
                ? { duration: 3, repeat: Infinity, ease: "easeInOut" }
                : { duration: 0.15 }
            }
          >
            <span
              className={
                voiceState === "listening"
                  ? "text-rose-400"
                  : voiceState === "speaking"
                  ? "text-teal-400"
                  : "text-indigo-300"
              }
            >
              {voiceState === "speaking" ? (
                <WaveformBars />
              ) : voiceState === "processing" ? (
                <ProcessingSpinner />
              ) : (
                <MicIcon />
              )}
            </span>
          </motion.button>

          <AnimatePresence>
            {isActive && (
              <motion.p
                className="absolute -bottom-7 left-1/2 -translate-x-1/2 whitespace-nowrap text-[11px] tracking-wider"
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                style={{
                  color:
                    voiceState === "listening"
                      ? "#fb7185"
                      : voiceState === "speaking"
                      ? "#2dd4bf"
                      : "#818cf8",
                }}
              >
                {voiceState === "listening" && "Listening..."}
                {voiceState === "processing" && "Thinking..."}
                {voiceState === "speaking" && "Speaking..."}
              </motion.p>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
