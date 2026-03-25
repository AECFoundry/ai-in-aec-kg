import type { GraphData, ChatResponse, UserInfo, ChatMessage } from "./types";

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

export async function register(
  name: string,
  email: string,
  company: string
): Promise<{ token: string }> {
  return request<{ token: string }>("/register", {
    method: "POST",
    body: JSON.stringify({ name, email, company }),
  });
}

export async function sendMessage(
  message: string,
  token: string
): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
  });
}

export async function getSession(token: string): Promise<UserInfo> {
  return request<UserInfo>("/session", {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
  });
}

export async function getChatHistory(token: string): Promise<ChatMessage[]> {
  return request<ChatMessage[]>("/chat/history", {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
  });
}
