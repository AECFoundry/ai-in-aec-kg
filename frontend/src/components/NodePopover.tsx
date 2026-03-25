import { useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAppStore } from "../stores/appStore";
import { nodeColors } from "../styles/theme";
import type { GraphNode, GraphLink } from "../lib/types";

function NodeContent({ node }: { node: GraphNode }) {
  const color = nodeColors[node.label] ?? "#8b5cf6";
  const filteredProps = Object.entries(node.properties).filter(
    ([key]) => key !== "embedding" && key !== "id"
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

  const isOpen = selectedNode !== null || selectedLink !== null;

  const handleClose = useCallback(() => {
    setSelectedNode(null);
    setSelectedLink(null);
  }, [setSelectedNode, setSelectedLink]);

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

            {selectedNode && <NodeContent node={selectedNode} />}
            {selectedLink && <LinkContent link={selectedLink} />}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
