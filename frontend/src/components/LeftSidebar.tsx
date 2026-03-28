import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAppStore } from "../stores/appStore";
import { nodeColors } from "../styles/theme";
import type { GraphNode } from "../lib/types";

const NODE_TYPE_ORDER = [
  "Session",
  "Presentation",
  "Speaker",
  "Organization",
  "Topic",
  "Technology",
  "Concept",
  "Project",
];

function SearchInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="relative">
      <svg
        className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Search nodes..."
        className="
          w-full pl-9 pr-3 py-2 rounded-xl
          bg-white/[0.04] border border-white/[0.06]
          text-sm text-slate-200 placeholder-slate-600
          outline-none focus:border-indigo-500/30 focus:bg-white/[0.06]
          transition-all duration-200
        "
      />
      {value && (
        <button
          onClick={() => onChange("")}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      )}
    </div>
  );
}

function NodeRow({
  node,
  isHighlighted,
  onClick,
  nodeRef,
}: {
  node: GraphNode;
  isHighlighted: boolean;
  onClick: () => void;
  nodeRef: (el: HTMLButtonElement | null) => void;
}) {
  const color = nodeColors[node.label] ?? "#8b5cf6";

  return (
    <button
      ref={nodeRef}
      onClick={onClick}
      className={`
        w-full flex items-center gap-2.5 px-3 py-1.5 text-left rounded-lg
        transition-all duration-150 group
        ${
          isHighlighted
            ? "bg-white/[0.08] border-l-2"
            : "hover:bg-white/[0.04] border-l-2 border-transparent"
        }
      `}
      style={
        isHighlighted ? { borderLeftColor: color } : undefined
      }
    >
      <span
        className="w-2 h-2 rounded-full shrink-0"
        style={{ backgroundColor: color }}
      />
      <span
        className={`text-[13px] truncate ${
          isHighlighted
            ? "text-white font-medium"
            : "text-slate-400 group-hover:text-slate-200"
        }`}
      >
        {node.name || node.id}
      </span>
    </button>
  );
}

function GroupSection({
  type,
  nodes,
  isCollapsed,
  onToggle,
  highlightedNodes,
  onNodeClick,
  nodeRefsMap,
  searchQuery,
}: {
  type: string;
  nodes: GraphNode[];
  isCollapsed: boolean;
  onToggle: () => void;
  highlightedNodes: Set<string>;
  onNodeClick: (id: string) => void;
  nodeRefsMap: React.MutableRefObject<Map<string, HTMLButtonElement>>;
  searchQuery: string;
}) {
  const color = nodeColors[type] ?? "#8b5cf6";
  const highlightedCount = nodes.filter((n) =>
    highlightedNodes.has(n.id)
  ).length;

  return (
    <div className="mb-1">
      <button
        onClick={onToggle}
        className="
          w-full flex items-center gap-2.5 px-4 py-2
          hover:bg-white/[0.03] transition-colors duration-150
          text-left
        "
      >
        <span
          className="w-2.5 h-2.5 rounded-full shrink-0"
          style={{ backgroundColor: color }}
        />
        <span className="text-[12px] font-semibold uppercase tracking-wider text-slate-400 flex-1">
          {type === "Technology" ? "Technologies" : `${type}s`}
        </span>
        {highlightedCount > 0 && (
          <span
            className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
            style={{
              backgroundColor: `${color}20`,
              color: color,
            }}
          >
            {highlightedCount}
          </span>
        )}
        <span className="text-[11px] text-slate-600 tabular-nums">
          {nodes.length}
        </span>
        <svg
          className={`text-slate-600 transition-transform duration-200 ${
            isCollapsed ? "" : "rotate-90"
          }`}
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
      </button>

      <AnimatePresence initial={false}>
        {!isCollapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="pl-2 pr-1 pb-1">
              {nodes.map((node) => (
                <NodeRow
                  key={node.id}
                  node={node}
                  isHighlighted={highlightedNodes.has(node.id)}
                  onClick={() => onNodeClick(node.id)}
                  nodeRef={(el) => {
                    if (el) nodeRefsMap.current.set(node.id, el);
                    else nodeRefsMap.current.delete(node.id);
                  }}
                />
              ))}
              {nodes.length === 0 && searchQuery && (
                <p className="text-[12px] text-slate-600 px-3 py-2">
                  No matches
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function LeftSidebar() {
  const graphData = useAppStore((s) => s.graphData);
  const highlightedNodes = useAppStore((s) => s.highlightedNodes);
  const collapsedGroups = useAppStore((s) => s.collapsedGroups);
  const scrollToNodeId = useAppStore((s) => s.scrollToNodeId);
  const toggleGroupCollapsed = useAppStore((s) => s.toggleGroupCollapsed);
  const setScrollToNodeId = useAppStore((s) => s.setScrollToNodeId);
  const focusNode = useAppStore((s) => s.focusNode);
  const clearHighlight = useAppStore((s) => s.clearHighlight);

  const [searchQuery, setSearchQuery] = useState("");
  const nodeRefsMap = useRef<Map<string, HTMLButtonElement>>(new Map());

  // Group and filter nodes
  const groupedNodes = useMemo(() => {
    if (!graphData) return {};
    const query = searchQuery.toLowerCase();
    const groups: Record<string, GraphNode[]> = {};

    for (const type of NODE_TYPE_ORDER) {
      const filtered = graphData.nodes
        .filter(
          (n) =>
            n.label === type &&
            (!query || n.name.toLowerCase().includes(query))
        )
        .sort((a, b) => a.name.localeCompare(b.name));
      if (filtered.length > 0 || !query) {
        groups[type] = filtered;
      }
    }
    return groups;
  }, [graphData, searchQuery]);

  const totalNodes = graphData?.nodes.length ?? 0;
  const totalLinks = graphData?.links.length ?? 0;

  // Scroll-to effect
  useEffect(() => {
    if (!scrollToNodeId) return;
    const el = nodeRefsMap.current.get(scrollToNodeId);
    if (el) {
      // Expand the parent group if collapsed
      const node = graphData?.nodes.find((n) => n.id === scrollToNodeId);
      if (node && collapsedGroups.has(node.label)) {
        toggleGroupCollapsed(node.label);
      }
      // Slight delay to allow group expansion animation
      requestAnimationFrame(() => {
        const target = nodeRefsMap.current.get(scrollToNodeId);
        target?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      });
    }
    setScrollToNodeId(null);
  }, [scrollToNodeId, graphData, collapsedGroups, toggleGroupCollapsed, setScrollToNodeId]);

  const handleNodeClick = useCallback(
    (nodeId: string) => {
      // Toggle: clicking an already-highlighted node deselects it
      if (highlightedNodes.size === 1 && highlightedNodes.has(nodeId)) {
        clearHighlight();
      } else {
        focusNode(nodeId);
      }
    },
    [focusNode, clearHighlight, highlightedNodes]
  );

  const isLoading = !graphData;

  return (
    <aside
      className="
        fixed top-0 left-0 h-full w-[320px] z-40
        bg-[#000011]/80 backdrop-blur-2xl
        border-r border-white/[0.06]
        flex flex-col
      "
    >
      {/* Header */}
      <div className="px-5 pt-5 pb-4 border-b border-white/[0.06]">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-base font-semibold text-white tracking-wide">
              AI in AEC 2026
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5 tracking-wider">
              {isLoading ? (
                <span className="inline-block w-32 h-3 rounded skeleton-shimmer" />
              ) : (
                <>{totalNodes} nodes &middot; {totalLinks} relationships</>
              )}
            </p>
          </div>
        </div>
        <SearchInput value={searchQuery} onChange={setSearchQuery} />
      </div>

      {/* Node groups */}
      <div className="flex-1 overflow-y-auto py-2 scrollbar-thin">
        {isLoading ? (
          <SkeletonGroups />
        ) : (
          NODE_TYPE_ORDER.map((type) => {
            const nodes = groupedNodes[type];
            if (!nodes && searchQuery) return null;
            return (
              <GroupSection
                key={type}
                type={type}
                nodes={nodes ?? []}
                isCollapsed={collapsedGroups.has(type)}
                onToggle={() => toggleGroupCollapsed(type)}
                highlightedNodes={highlightedNodes}
                onNodeClick={handleNodeClick}
                nodeRefsMap={nodeRefsMap}
                searchQuery={searchQuery}
              />
            );
          })
        )}
      </div>

      {/* Footer — Powered by logo */}
      <div className="px-5 py-4 border-t border-white/[0.06]">
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-600 uppercase tracking-widest">
            Powered by
          </span>
          <img
            src="/logo.png"
            alt="AECFoundry"
            className="h-4 opacity-50"
          />
        </div>
      </div>
    </aside>
  );
}

function SkeletonGroups() {
  return (
    <div className="px-4 py-2 space-y-4">
      {NODE_TYPE_ORDER.map((type) => (
        <div key={type} className="space-y-2">
          <div className="flex items-center gap-2.5 py-1">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0 opacity-30"
              style={{ backgroundColor: nodeColors[type] ?? "#8b5cf6" }}
            />
            <div className="w-20 h-3 rounded skeleton-shimmer" />
            <div className="ml-auto w-6 h-3 rounded skeleton-shimmer" />
          </div>
          <div className="pl-5 space-y-1.5">
            {[75, 60, 85].map((w, i) => (
              <div
                key={i}
                className="h-3 rounded skeleton-shimmer"
                style={{ width: `${w}%` }}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
