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
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  subgraph?: SubgraphHighlight;
  sources?: SourceRef[];
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
