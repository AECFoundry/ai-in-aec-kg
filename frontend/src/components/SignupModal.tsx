import { useState, useCallback } from "react";
import type { FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAppStore } from "../stores/appStore";
import { register } from "../lib/api";
import { useChat } from "../hooks/useChat";

export default function SignupModal() {
  const showSignup = useAppStore((s) => s.showSignup);
  const setShowSignup = useAppStore((s) => s.setShowSignup);
  const pendingQuestion = useAppStore((s) => s.pendingQuestion);
  const setPendingQuestion = useAppStore((s) => s.setPendingQuestion);
  const setAuth = useAppStore((s) => s.setAuth);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { sendMessage } = useChat();

  const handleSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      if (!name.trim() || !email.trim() || !company.trim()) {
        setError("All fields are required.");
        return;
      }

      setSubmitting(true);
      setError(null);

      try {
        const { token } = await register(name.trim(), email.trim(), company.trim());
        setAuth(token, {
          name: name.trim(),
          email: email.trim(),
          company: company.trim(),
        });
        setShowSignup(false);

        // Send the pending question now
        if (pendingQuestion) {
          const q = pendingQuestion;
          setPendingQuestion(null);
          // Use a small delay so the store updates propagate
          setTimeout(() => sendMessage(q), 50);
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Registration failed. Please try again."
        );
      } finally {
        setSubmitting(false);
      }
    },
    [name, email, company, setAuth, setShowSignup, pendingQuestion, setPendingQuestion, sendMessage]
  );

  const handleClose = useCallback(() => {
    setShowSignup(false);
    setPendingQuestion(null);
  }, [setShowSignup, setPendingQuestion]);

  return (
    <AnimatePresence>
      {showSignup && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 bg-black/60"
            onClick={handleClose}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 30 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 30 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className="
              fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
              w-[420px]
              bg-[#0a0a1a]/90 backdrop-blur-2xl
              border border-white/[0.08]
              rounded-2xl
              p-8
              shadow-2xl shadow-black/50
            "
          >
            {/* Header */}
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 mb-4">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#6366f1"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="12" r="3" />
                  <circle cx="5" cy="6" r="2" />
                  <circle cx="19" cy="6" r="2" />
                  <circle cx="5" cy="18" r="2" />
                  <circle cx="19" cy="18" r="2" />
                  <line x1="12" y1="9" x2="12" y2="3" />
                  <line x1="9.5" y1="13" x2="6.5" y2="16.5" />
                  <line x1="14.5" y1="13" x2="17.5" y2="16.5" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-white tracking-wide">
                Welcome, Explorer
              </h2>
              <p className="text-sm text-slate-400 mt-2">
                Sign up to start exploring the AI in AEC knowledge graph
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-[11px] uppercase tracking-wider text-slate-400 mb-1.5">
                  Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="
                    w-full px-4 py-3 rounded-xl
                    bg-white/[0.04] border border-white/[0.08]
                    text-white text-sm placeholder-slate-500
                    outline-none
                    focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/25
                    transition-all duration-200
                  "
                  placeholder="Your name"
                />
              </div>

              <div>
                <label className="block text-[11px] uppercase tracking-wider text-slate-400 mb-1.5">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="
                    w-full px-4 py-3 rounded-xl
                    bg-white/[0.04] border border-white/[0.08]
                    text-white text-sm placeholder-slate-500
                    outline-none
                    focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/25
                    transition-all duration-200
                  "
                  placeholder="your@email.com"
                />
              </div>

              <div>
                <label className="block text-[11px] uppercase tracking-wider text-slate-400 mb-1.5">
                  Company
                </label>
                <input
                  type="text"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  className="
                    w-full px-4 py-3 rounded-xl
                    bg-white/[0.04] border border-white/[0.08]
                    text-white text-sm placeholder-slate-500
                    outline-none
                    focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/25
                    transition-all duration-200
                  "
                  placeholder="Your company"
                />
              </div>

              {error && (
                <p className="text-red-400 text-sm text-center">{error}</p>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="
                  w-full py-3.5 rounded-xl
                  bg-indigo-600 hover:bg-indigo-500
                  text-white text-sm font-medium tracking-wide
                  transition-all duration-300
                  disabled:opacity-50 disabled:cursor-not-allowed
                  hover:shadow-lg hover:shadow-indigo-500/25
                  active:scale-[0.98]
                  mt-6
                "
              >
                {submitting ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Registering...
                  </span>
                ) : (
                  "Start Exploring"
                )}
              </button>
            </form>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
