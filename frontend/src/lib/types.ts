export interface GraphNode {
  id: string;
  label: string;
  name: string;
  group: string;
  properties: Record<string, unknown>;
  // Added by force-graph at runtime:
  x?: number;
  y?: number;
  z?: number;
  __threeObj?: unknown;
}

export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  type: string;
  properties: Record<string, unknown>;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface SourceRef {
  id: string;
  name: string;
  label: string;
  score: number;
  citation?: number;
}

export interface AgentTraceStep {
  type: "thinking" | "tool_call" | "tool_progress" | "tool_result";
  tool?: string;
  detail: string;
}

export interface ChatMessage {
  id?: string;
  role: "user" | "assistant";
  content: string;
  subgraph?: SubgraphHighlight;
  sources?: SourceRef[];
  agentTrace?: AgentTraceStep[];
  isStreaming?: boolean;
}

export interface SubgraphHighlight {
  node_ids: string[];
  link_ids: string[];
}

export interface UserInfo {
  name: string;
  email: string;
  company: string;
}

export interface ChatResponse {
  answer: string;
  subgraph?: SubgraphHighlight;
  sources?: SourceRef[];
}
