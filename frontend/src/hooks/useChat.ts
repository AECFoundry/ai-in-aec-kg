import { useCallback } from "react";
import { sendMessage as apiSendMessage } from "../lib/api";
import { useAppStore } from "../stores/appStore";

export function useChat() {
  const token = useAppStore((s) => s.token);
  const addMessage = useAppStore((s) => s.addMessage);
  const setLoading = useAppStore((s) => s.setLoading);
  const setSidebarOpen = useAppStore((s) => s.setSidebarOpen);
  const setHighlight = useAppStore((s) => s.setHighlight);
  const setShowSignup = useAppStore((s) => s.setShowSignup);
  const setPendingQuestion = useAppStore((s) => s.setPendingQuestion);
  const isLoading = useAppStore((s) => s.isLoading);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      // If not authenticated, save the question and show signup
      if (!token) {
        setPendingQuestion(trimmed);
        setShowSignup(true);
        return;
      }

      // Add user message
      addMessage({ role: "user", content: trimmed });
      setSidebarOpen(true);
      setLoading(true);

      try {
        const response = await apiSendMessage(trimmed, token);

        addMessage({
          role: "assistant",
          content: response.answer,
          subgraph: response.subgraph,
          sources: response.sources,
        });

        // Update highlighted subgraph
        if (response.subgraph) {
          setHighlight(
            response.subgraph.node_ids ?? [],
            response.subgraph.link_ids ?? []
          );
        }
      } catch (err) {
        console.error("Chat error:", err);
        addMessage({
          role: "assistant",
          content:
            "Sorry, something went wrong. Please try again.",
        });
      } finally {
        setLoading(false);
      }
    },
    [
      token,
      addMessage,
      setLoading,
      setSidebarOpen,
      setHighlight,
      setShowSignup,
      setPendingQuestion,
    ]
  );

  return { sendMessage, isLoading };
}
