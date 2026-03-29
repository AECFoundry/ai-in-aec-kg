import { useCallback } from "react";
import { sendMessageStream, type SSEEvent } from "../lib/api";
import { useAppStore } from "../stores/appStore";
import type { AgentTraceStep } from "../lib/types";

let msgCounter = 0;

export interface SendMessageOptions {
  voiceInitiated?: boolean;
}

export function useChat() {
  const isLoading = useAppStore((s) => s.isLoading);

  const sendMessage = useCallback(
    async (text: string, options?: SendMessageOptions) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      const {
        token,
        addMessage,
        updateMessage,
        setLoading,
        setSidebarOpen,
        focusSubgraph,
        clearHighlight,
        setShowSignup,
        setPendingQuestion,
        setPendingTTS,
      } = useAppStore.getState();

      if (!token) {
        setPendingQuestion(trimmed);
        setShowSignup(true);
        return;
      }

      addMessage({ role: "user", content: trimmed });
      setSidebarOpen(true);
      setLoading(true);
      clearHighlight();

      // Create a placeholder streaming message
      const msgId = `assistant-${++msgCounter}`;
      addMessage({
        id: msgId,
        role: "assistant",
        content: "",
        agentTrace: [],
        isStreaming: true,
      });

      // Set pendingTTS AFTER the new assistant message exists in the store,
      // so the subscription won't accidentally trigger on a previous message.
      if (options?.voiceInitiated) {
        setPendingTTS(true);
      }

      let contentSoFar = "";
      let spokenSoFar = "";
      const trace: AgentTraceStep[] = [];

      try {
        await sendMessageStream(trimmed, token, (event: SSEEvent) => {
          const { updateMessage: update, focusSubgraph: focus } =
            useAppStore.getState();

          switch (event.event) {
            case "thinking":
            case "tool_call":
            case "tool_progress":
            case "tool_result": {
              trace.push({
                type: event.data.type as AgentTraceStep["type"],
                tool: "tool" in event.data ? event.data.tool : undefined,
                detail: event.data.detail,
              });
              update(msgId, { agentTrace: [...trace] });
              break;
            }
            case "graph_update": {
              const { addHighlight } = useAppStore.getState();
              addHighlight(
                event.data.node_ids ?? [],
                event.data.link_ids ?? [],
              );
              break;
            }
            case "token": {
              contentSoFar += event.data.content;
              update(msgId, { content: contentSoFar });
              break;
            }
            case "spoken_token": {
              spokenSoFar += event.data.content;
              update(msgId, { spokenAnswer: spokenSoFar });
              break;
            }
            case "done": {
              const { answer, subgraph, sources, spoken_answer } = event.data;
              // Use spoken_token-built value if available, otherwise fall back
              // to the done event's spoken_answer (covers remount edge cases).
              const currentMsg = useAppStore.getState().messages.find(
                (m) => m.id === msgId,
              );
              const finalSpoken =
                currentMsg?.spokenAnswer || spoken_answer || "";
              update(msgId, {
                content: answer,
                spokenAnswer: finalSpoken,
                subgraph: subgraph,
                sources: sources,
                isStreaming: false,
              });
              if (subgraph) {
                focus(
                  subgraph.node_ids ?? [],
                  subgraph.link_ids ?? [],
                );
              }
              break;
            }
            case "error": {
              update(msgId, {
                content: "Sorry, something went wrong. Please try again.",
                isStreaming: false,
              });
              break;
            }
          }
        });
      } catch (err) {
        console.error("Chat stream error:", err);
        useAppStore.getState().updateMessage(msgId, {
          content: "Sorry, something went wrong. Please try again.",
          isStreaming: false,
        });
      } finally {
        useAppStore.getState().setLoading(false);
      }
    },
    [],
  );

  return { sendMessage, isLoading };
}
