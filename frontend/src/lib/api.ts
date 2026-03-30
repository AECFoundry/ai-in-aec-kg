import type { GraphData, ChatResponse, ChatMessage } from "./types";

const BASE = "/api";

async function request<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: {
      "Content-Type": "application/json",
      ...((options?.headers as Record<string, string>) ?? {}),
    },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }

  return res.json() as Promise<T>;
}

export async function fetchGraph(): Promise<GraphData> {
  return request<GraphData>("/graph");
}

export async function sendMessage(
  message: string,
): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export async function getChatHistory(): Promise<ChatMessage[]> {
  return request<ChatMessage[]>("/chat/history");
}

export type SSEEvent =
  | { event: "thinking"; data: { type: string; detail: string } }
  | { event: "tool_call"; data: { type: string; tool: string; detail: string } }
  | { event: "tool_progress"; data: { type: string; tool: string; detail: string } }
  | { event: "tool_result"; data: { type: string; tool: string; detail: string } }
  | { event: "graph_update"; data: { type: string; node_ids: string[]; link_ids: string[] } }
  | { event: "token"; data: { content: string } }
  | { event: "spoken_token"; data: { type: string; content: string } }
  | { event: "done"; data: ChatResponse }
  | { event: "error"; data: { detail: string } };

export async function fetchVoiceCapabilities(): Promise<{ tts_available: boolean }> {
  return request<{ tts_available: boolean }>("/voice/capabilities");
}

export async function fetchTTS(
  text: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const res = await fetch(`${BASE}/voice/tts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text }),
    signal,
  });
  if (!res.ok) throw new Error(`TTS error ${res.status}`);
  return res.blob();
}

export async function sendMessageStream(
  message: string,
  onEvent: (event: SSEEvent) => void,
): Promise<void> {
  const res = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.startsWith("event:")) {
        currentEvent = line.slice(6).trim();
      } else if (line.startsWith("data:") && currentEvent) {
        try {
          const data = JSON.parse(line.slice(5).trim());
          onEvent({ event: currentEvent, data } as SSEEvent);
        } catch {
          // Skip malformed JSON
        }
        currentEvent = "";
      } else if (line === "") {
        currentEvent = "";
      }
    }
  }
}
