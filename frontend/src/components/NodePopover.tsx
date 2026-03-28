import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAppStore } from "../stores/appStore";
import { nodeColors } from "../styles/theme";
import type { GraphNode, GraphLink } from "../lib/types";

/** Keys to hide from the generic property list (shown elsewhere or redundant). */
const HIDDEN_KEYS = new Set(["embedding", "id", "name", "title"]);
/** For Session nodes these are also redundant since we show summary_text directly. */
const SESSION_HIDDEN_KEYS = new Set([
  ...HIDDEN_KEYS,
  "summary_text",
  "description",
  "session_number",
]);
/** For Presentation nodes — everything shown via dedicated UI. */
const PRESENTATION_HIDDEN_KEYS = new Set([
  ...HIDDEN_KEYS,
  "summary",
  "description",
  "detailed_summary",
  "session_id",
  "order",
]);

const SUMMARY_COLLAPSED_LEN = 180;
const DETAILED_SUMMARY_COLLAPSED_LEN = 300;

/** Find Topic nodes connected via COVERS_TOPIC from a given node. */
function useLinkedTopics(nodeId: string): string[] {
  const graphData = useAppStore((s) => s.graphData);
  if (!graphData) return [];
  const topics: string[] = [];
  for (const link of graphData.links) {
    if (link.type !== "COVERS_TOPIC") continue;
    const sourceId = typeof link.source === "string" ? link.source : (link.source as GraphNode).id;
    if (sourceId !== nodeId) continue;
    const targetId = typeof link.target === "string" ? link.target : (link.target as GraphNode).id;
    const topicNode = graphData.nodes.find((n) => n.id === targetId && n.label === "Topic");
    if (topicNode) topics.push(topicNode.name);
  }
  return topics;
}

function TopicBadges({ nodeId }: { nodeId: string }) {
  const topics = useLinkedTopics(nodeId);
  if (topics.length === 0) return null;
  const topicColor = nodeColors.Topic ?? "#f43f5e";
  return (
    <div className="mb-4">
      <h4 className="text-[11px] uppercase tracking-wider text-slate-500 mb-2">Topics</h4>
      <div className="flex flex-wrap gap-1.5">
        {topics.map((t) => (
          <span
            key={t}
            className="px-2 py-0.5 rounded-full text-[11px] font-medium"
            style={{
              backgroundColor: `${topicColor}15`,
              color: topicColor,
              border: `1px solid ${topicColor}25`,
            }}
          >
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

function SessionContent({
  node,
  onNavigate,
}: {
  node: GraphNode;
  onNavigate: (nodeId: string) => void;
}) {
  const graphData = useAppStore((s) => s.graphData);
  const color = nodeColors.Session;
  const [expanded, setExpanded] = useState(false);

  const summary =
    (node.properties.summary_text as string) ??
    (node.properties.description as string) ??
    "";
  const needsTruncation = summary.length > SUMMARY_COLLAPSED_LEN;

  // Find linked presentations (PART_OF -> this session), sorted by order
  const presentations: GraphNode[] = [];
  if (graphData) {
    const presLinks = graphData.links.filter(
      (l) =>
        l.type === "PART_OF" &&
        (typeof l.target === "string" ? l.target : (l.target as GraphNode).id) === node.id,
    );
    for (const link of presLinks) {
      const sourceId =
        typeof link.source === "string" ? link.source : (link.source as GraphNode).id;
      const presNode = graphData.nodes.find((n) => n.id === sourceId);
      if (presNode) presentations.push(presNode);
    }
    presentations.sort(
      (a, b) => ((a.properties.order as number) ?? 0) - ((b.properties.order as number) ?? 0),
    );
  }

  const presColor = nodeColors.Presentation;

  const extraProps = Object.entries(node.properties).filter(
    ([key]) => !SESSION_HIDDEN_KEYS.has(key)
  );

  return (
    <>
      <div className="flex items-center gap-3 mb-4">
        <span
          className="px-2.5 py-1 rounded-full text-[11px] font-medium uppercase tracking-wider"
          style={{
            backgroundColor: `${color}20`,
            color: color,
            border: `1px solid ${color}40`,
          }}
        >
          Session
        </span>
      </div>

      <h3 className="text-lg font-semibold text-white mb-4 leading-snug">
        {node.name || node.id}
      </h3>

      {summary && (
        <div className="mb-4">
          <p className="text-sm text-slate-300 leading-relaxed">
            {expanded || !needsTruncation
              ? summary
              : `${summary.slice(0, SUMMARY_COLLAPSED_LEN).trimEnd()}...`}
          </p>
          {needsTruncation && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="mt-1.5 text-[12px] text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              {expanded ? "Show less" : "Read more"}
            </button>
          )}
        </div>
      )}

      <TopicBadges nodeId={node.id} />

      {presentations.length > 0 && (
        <div className="mb-4">
          <h4 className="text-[11px] uppercase tracking-wider text-slate-500 mb-2">
            Presentations
          </h4>
          <div className="space-y-1">
            {presentations.map((pres) => (
              <button
                key={pres.id}
                onClick={() => onNavigate(pres.id)}
                className="
                  flex items-center gap-2 w-full px-3 py-2
                  rounded-xl bg-white/[0.04] border border-white/[0.06]
                  hover:bg-white/[0.08] hover:border-white/[0.1]
                  transition-all duration-200 group text-left
                "
              >
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: presColor }}
                />
                <span className="flex-1 text-sm text-slate-300 group-hover:text-white transition-colors">
                  {pres.name}
                </span>
                <svg
                  className="text-slate-600 group-hover:text-slate-400 transition-colors shrink-0"
                  width="14"
                  height="14"
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
            ))}
          </div>
        </div>
      )}

      {extraProps.length > 0 && (
        <div className="space-y-2.5">
          {extraProps.map(([key, value]) => (
            <div key={key}>
              <dt className="text-[11px] uppercase tracking-wider text-slate-500 mb-0.5">
                {key.replace(/_/g, " ")}
              </dt>
              <dd className="text-sm text-slate-300 leading-relaxed">
                {typeof value === "string" ? value : JSON.stringify(value)}
              </dd>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function PresentationContent({
  node,
  onNavigate,
}: {
  node: GraphNode;
  onNavigate: (nodeId: string) => void;
}) {
  const graphData = useAppStore((s) => s.graphData);
  const color = nodeColors.Presentation;
  const [detailExpanded, setDetailExpanded] = useState(false);

  const summary =
    (node.properties.summary as string) ??
    (node.properties.description as string) ??
    "";

  const detailedSummary = (node.properties.detailed_summary as string) ?? "";
  const detailNeedsTruncation = detailedSummary.length > DETAILED_SUMMARY_COLLAPSED_LEN;

  // Find speakers from PRESENTED_BY links
  const speakers: string[] = [];
  if (graphData) {
    const speakerLinks = graphData.links.filter(
      (l) =>
        l.type === "PRESENTED_BY" &&
        (typeof l.source === "string" ? l.source : (l.source as GraphNode).id) === node.id,
    );
    for (const link of speakerLinks) {
      const targetId =
        typeof link.target === "string" ? link.target : (link.target as GraphNode).id;
      const speakerNode = graphData.nodes.find((n) => n.id === targetId);
      if (speakerNode) speakers.push(speakerNode.name);
    }
  }

  // Find parent session
  const sessionId = node.properties.session_id as string | undefined;
  const sessionNode = graphData?.nodes.find(
    (n) => n.id === sessionId && n.label === "Session",
  );

  const extraProps = Object.entries(node.properties).filter(
    ([key]) => !PRESENTATION_HIDDEN_KEYS.has(key),
  );

  return (
    <>
      <div className="flex items-center gap-3 mb-4">
        <span
          className="px-2.5 py-1 rounded-full text-[11px] font-medium uppercase tracking-wider"
          style={{
            backgroundColor: `${color}20`,
            color: color,
            border: `1px solid ${color}40`,
          }}
        >
          Presentation
        </span>
      </div>

      <h3 className="text-lg font-semibold text-white mb-3 leading-snug">
        {node.name || node.id}
      </h3>

      {speakers.length > 0 && (
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <svg
            className="text-slate-500 shrink-0"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
          <span className="text-sm text-slate-300">
            {speakers.join(", ")}
          </span>
        </div>
      )}

      {/* Short summary — always visible */}
      {summary && (
        <p className="text-sm text-slate-300 leading-relaxed mb-3">{summary}</p>
      )}

      {/* Detailed summary — expandable */}
      {detailedSummary && (
        <div className="mb-4">
          <button
            onClick={() => setDetailExpanded((v) => !v)}
            className="text-[12px] text-indigo-400 hover:text-indigo-300 transition-colors mb-2"
          >
            {detailExpanded ? "Hide detailed summary" : "Detailed summary..."}
          </button>
          {detailExpanded && (
            <p className="text-sm text-slate-400 leading-relaxed">
              {detailNeedsTruncation && !detailExpanded
                ? `${detailedSummary.slice(0, DETAILED_SUMMARY_COLLAPSED_LEN).trimEnd()}...`
                : detailedSummary}
            </p>
          )}
        </div>
      )}

      <TopicBadges nodeId={node.id} />

      {sessionNode && (
        <button
          onClick={() => onNavigate(sessionNode.id)}
          className="
            flex items-center gap-2 w-full px-3 py-2.5 mb-4
            rounded-xl bg-white/[0.04] border border-white/[0.06]
            hover:bg-white/[0.08] hover:border-white/[0.1]
            transition-all duration-200 group text-left
          "
        >
          <span
            className="w-2.5 h-2.5 rounded-full shrink-0"
            style={{ backgroundColor: nodeColors.Session }}
          />
          <span className="flex-1 text-sm text-slate-300 group-hover:text-white transition-colors truncate">
            {sessionNode.name}
          </span>
          <svg
            className="text-slate-600 group-hover:text-slate-400 transition-colors shrink-0"
            width="14"
            height="14"
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
      )}

      {extraProps.length > 0 && (
        <div className="space-y-2.5">
          {extraProps.map(([key, value]) => (
            <div key={key}>
              <dt className="text-[11px] uppercase tracking-wider text-slate-500 mb-0.5">
                {key.replace(/_/g, " ")}
              </dt>
              <dd className="text-sm text-slate-300 leading-relaxed">
                {typeof value === "string" ? value : JSON.stringify(value)}
              </dd>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function NodeContent({ node, onNavigate }: { node: GraphNode; onNavigate: (nodeId: string) => void }) {
  if (node.label === "Session") return <SessionContent node={node} onNavigate={onNavigate} />;
  if (node.label === "Presentation") return <PresentationContent node={node} onNavigate={onNavigate} />;

  const color = nodeColors[node.label] ?? "#8b5cf6";
  const filteredProps = Object.entries(node.properties).filter(
    ([key]) => !HIDDEN_KEYS.has(key)
  );

  return (
    <>
      <div className="flex items-center gap-3 mb-4">
        <span
          className="px-2.5 py-1 rounded-full text-[11px] font-medium uppercase tracking-wider"
          style={{
            backgroundColor: `${color}20`,
            color: color,
            border: `1px solid ${color}40`,
          }}
        >
          {node.label}
        </span>
      </div>

      <h3 className="text-lg font-semibold text-white mb-4 leading-snug">
        {node.name || node.id}
      </h3>

      {filteredProps.length > 0 && (
        <div className="space-y-2.5">
          {filteredProps.map(([key, value]) => (
            <div key={key}>
              <dt className="text-[11px] uppercase tracking-wider text-slate-500 mb-0.5">
                {key.replace(/_/g, " ")}
              </dt>
              <dd className="text-sm text-slate-300 leading-relaxed">
                {typeof value === "string"
                  ? value.length > 200
                    ? `${value.slice(0, 200)}...`
                    : value
                  : JSON.stringify(value)}
              </dd>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function LinkContent({ link }: { link: GraphLink }) {
  const sourceName =
    typeof link.source === "string"
      ? link.source
      : (link.source as GraphNode).name ?? (link.source as GraphNode).id;
  const targetName =
    typeof link.target === "string"
      ? link.target
      : (link.target as GraphNode).name ?? (link.target as GraphNode).id;

  const filteredProps = Object.entries(link.properties ?? {}).filter(
    ([key]) => key !== "embedding"
  );

  return (
    <>
      <div className="flex items-center gap-3 mb-4">
        <span className="px-2.5 py-1 rounded-full text-[11px] font-medium uppercase tracking-wider bg-white/[0.06] text-slate-300 border border-white/[0.1]">
          Relationship
        </span>
      </div>

      <div className="flex items-center gap-2 mb-4 text-sm">
        <span className="text-white font-medium">{sourceName}</span>
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-[11px] tracking-wider uppercase">
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <line x1="5" y1="12" x2="19" y2="12" />
            <polyline points="12 5 19 12 12 19" />
          </svg>
          {link.type}
        </span>
        <span className="text-white font-medium">{targetName}</span>
      </div>

      {filteredProps.length > 0 && (
        <div className="space-y-2.5">
          {filteredProps.map(([key, value]) => (
            <div key={key}>
              <dt className="text-[11px] uppercase tracking-wider text-slate-500 mb-0.5">
                {key.replace(/_/g, " ")}
              </dt>
              <dd className="text-sm text-slate-300 leading-relaxed">
                {typeof value === "string" ? value : JSON.stringify(value)}
              </dd>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

export default function NodePopover() {
  const selectedNode = useAppStore((s) => s.selectedNode);
  const selectedLink = useAppStore((s) => s.selectedLink);
  const setSelectedNode = useAppStore((s) => s.setSelectedNode);
  const setSelectedLink = useAppStore((s) => s.setSelectedLink);
  const focusNode = useAppStore((s) => s.focusNode);
  const clearHighlight = useAppStore((s) => s.clearHighlight);

  const isOpen = selectedNode !== null || selectedLink !== null;

  const handleClose = useCallback(() => {
    setSelectedNode(null);
    setSelectedLink(null);
    clearHighlight();
  }, [setSelectedNode, setSelectedLink, clearHighlight]);

  const graphData = useAppStore((s) => s.graphData);

  const handleNavigate = useCallback(
    (nodeId: string) => {
      handleClose();
      focusNode(nodeId);
      // Open card after camera arrives (matches GraphCanvas click behavior)
      const targetNode = graphData?.nodes.find((n) => n.id === nodeId);
      if (targetNode) {
        setTimeout(() => setSelectedNode(targetNode), 1500);
      }
    },
    [handleClose, focusNode, graphData, setSelectedNode],
  );

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;

    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, handleClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 bg-black/40"
            onClick={handleClose}
          />

          {/* Popover card */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className="
              fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
              w-[440px] max-h-[70vh] overflow-y-auto
              bg-[#0a0a1a]/90 backdrop-blur-2xl
              border border-white/[0.08]
              rounded-2xl
              p-6
              shadow-2xl shadow-black/50
            "
          >
            {/* Close button */}
            <button
              onClick={handleClose}
              className="
                absolute top-4 right-4
                p-1.5 rounded-lg
                hover:bg-white/[0.06]
                text-slate-500 hover:text-white
                transition-all duration-200
              "
            >
              <svg
                width="16"
                height="16"
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

            {selectedNode && <NodeContent node={selectedNode} onNavigate={handleNavigate} />}
            {selectedLink && <LinkContent link={selectedLink} />}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
