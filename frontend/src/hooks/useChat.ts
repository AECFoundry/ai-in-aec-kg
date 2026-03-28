import { useCallback } from "react";
import { sendMessageStream, type SSEEvent } from "../lib/api";
import { useAppStore } from "../stores/appStore";
import type { AgentTraceStep } from "../lib/types";

let msgCounter = 0;

export function useChat() {
  const isLoading = useAppStore((s) => s.isLoading);

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    const {
      token,
      addMessage,
      updateMessage,
      setLoading,
      setSidebarOpen,
      focusSubgraph,
      setShowSignup,
      setPendingQuestion,
    } = useAppStore.getState();

    if (!token) {
      setPendingQuestion(trimmed);
      setShowSignup(true);
      return;
    }

    addMessage({ role: "user", content: trimmed });
    setSidebarOpen(true);
    setLoading(true);

    // Create a placeholder streaming message
    const msgId = `assistant-${++msgCounter}`;
    addMessage({
      id: msgId,
      role: "assistant",
      content: "",
      agentTrace: [],
      isStreaming: true,
    });

    let contentSoFar = "";
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
          case "token": {
            contentSoFar += event.data.content;
            update(msgId, { content: contentSoFar });
            break;
          }
          case "done": {
            const { answer, subgraph, sources } = event.data;
            update(msgId, {
              content: answer,
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
  }, []);

  return { sendMessage, isLoading };
}
