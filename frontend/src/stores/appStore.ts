import { create } from "zustand";
import type { GraphData, GraphNode, GraphLink, ChatMessage } from "../lib/types";

interface AppState {
  // Chat
  sidebarOpen: boolean;
  messages: ChatMessage[];
  isLoading: boolean;
  setSidebarOpen: (open: boolean) => void;
  addMessage: (msg: ChatMessage) => void;
  updateMessage: (id: string, partial: Partial<ChatMessage>) => void;
  setMessages: (msgs: ChatMessage[]) => void;
  setLoading: (loading: boolean) => void;

  // Graph
  graphData: GraphData | null;
  setGraphData: (data: GraphData) => void;
  highlightedNodes: Set<string>;
  highlightedLinks: Set<string>;
  setHighlight: (nodes: string[], links: string[]) => void;
  addHighlight: (nodes: string[], links: string[]) => void;
  clearHighlight: () => void;

  // Linked selection
  flyToNodeId: string | null;
  scrollToNodeId: string | null;
  collapsedGroups: Set<string>;
  setFlyToNodeId: (id: string | null) => void;
  setScrollToNodeId: (id: string | null) => void;
  toggleGroupCollapsed: (group: string) => void;
  focusNode: (nodeId: string) => void;
  focusSubgraph: (nodeIds: string[], linkIds: string[]) => void;

  // Selection
  selectedNode: GraphNode | null;
  selectedLink: GraphLink | null;
  setSelectedNode: (node: GraphNode | null) => void;
  setSelectedLink: (link: GraphLink | null) => void;

  // Voice
  voiceState: 'idle' | 'listening' | 'processing' | 'speaking';
  ttsAvailable: boolean;
  pendingTTS: boolean;
  setVoiceState: (state: 'idle' | 'listening' | 'processing' | 'speaking') => void;
  setTtsAvailable: (available: boolean) => void;
  setPendingTTS: (pending: boolean) => void;

  // Theme
  theme: 'light' | 'dark';
  toggleTheme: () => void;
}

export type { AppState };

export const useAppStore = create<AppState>()((set) => ({
  // Chat
  sidebarOpen: false,
  messages: [],
  isLoading: false,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  addMessage: (msg) =>
    set((state) => ({ messages: [...state.messages, msg] })),
  updateMessage: (id, partial) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, ...partial } : m
      ),
    })),
  setMessages: (msgs) => set({ messages: msgs }),
  setLoading: (loading) => set({ isLoading: loading }),

  // Graph
  graphData: null,
  setGraphData: (data) => set({ graphData: data }),
  highlightedNodes: new Set<string>(),
  highlightedLinks: new Set<string>(),
  setHighlight: (nodes, links) =>
    set({
      highlightedNodes: new Set(nodes),
      highlightedLinks: new Set(links),
    }),
  addHighlight: (nodes, links) =>
    set((state) => ({
      highlightedNodes: new Set([...state.highlightedNodes, ...nodes]),
      highlightedLinks: new Set([...state.highlightedLinks, ...links]),
    })),
  clearHighlight: () =>
    set({
      highlightedNodes: new Set<string>(),
      highlightedLinks: new Set<string>(),
      flyToNodeId: null,
      scrollToNodeId: null,
    }),

  // Linked selection
  flyToNodeId: null,
  scrollToNodeId: null,
  collapsedGroups: new Set<string>([
    "Session", "Presentation", "Speaker", "Organization",
    "Topic", "Technology", "Concept", "Project",
  ]),
  setFlyToNodeId: (id) => set({ flyToNodeId: id }),
  setScrollToNodeId: (id) => set({ scrollToNodeId: id }),
  toggleGroupCollapsed: (group) =>
    set((state) => {
      const next = new Set(state.collapsedGroups);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return { collapsedGroups: next };
    }),
  focusNode: (nodeId) =>
    set({
      highlightedNodes: new Set([nodeId]),
      highlightedLinks: new Set<string>(),
      scrollToNodeId: nodeId,
      flyToNodeId: nodeId,
    }),
  focusSubgraph: (nodeIds, linkIds) =>
    set({
      highlightedNodes: new Set(nodeIds),
      highlightedLinks: new Set(linkIds),
    }),

  // Selection
  selectedNode: null,
  selectedLink: null,
  setSelectedNode: (node) => set({ selectedNode: node, selectedLink: null }),
  setSelectedLink: (link) => set({ selectedLink: link, selectedNode: null }),

  // Voice
  voiceState: 'idle' as const,
  ttsAvailable: false,
  pendingTTS: false,
  setVoiceState: (state) => set({ voiceState: state }),
  setTtsAvailable: (available) => set({ ttsAvailable: available }),
  setPendingTTS: (pending) => set({ pendingTTS: pending }),

  // Theme
  theme: localStorage.getItem('theme') === 'dark' ? 'dark' as const : 'light' as const,
  toggleTheme: () => set((state) => {
    const next = state.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('theme', next);
    return { theme: next };
  }),
}));
