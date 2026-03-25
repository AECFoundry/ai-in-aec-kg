import { useRef, useCallback, useEffect, useMemo } from "react";
import ForceGraph3D from "react-force-graph-3d";
import SpriteText from "three-spritetext";
import * as THREE from "three";
import { useAppStore } from "../stores/appStore";
import { useGraphData } from "../hooks/useGraphData";
import { nodeColors, nodeSizes } from "../styles/theme";
import type { GraphNode, GraphLink } from "../lib/types";

const LABEL_VISIBLE_DISTANCE = 300;
const DEFAULT_NODE_COLOR = "#8b5cf6";
const DEFAULT_NODE_SIZE = 3;

export default function GraphCanvas() {
  const graphRef = useRef<any>(null); // eslint-disable-line @typescript-eslint/no-explicit-any
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const highlightedNodes = useAppStore((s) => s.highlightedNodes);
  const highlightedLinks = useAppStore((s) => s.highlightedLinks);
  const setSelectedNode = useAppStore((s) => s.setSelectedNode);
  const setSelectedLink = useAppStore((s) => s.setSelectedLink);
  const graphData = useGraphData();

  const hasHighlight = highlightedNodes.size > 0 || highlightedLinks.size > 0;

  // Auto-rotation
  useEffect(() => {
    const fg = graphRef.current;
    if (!fg) return;

    const controls = fg.controls?.();
    if (controls) {
      controls.autoRotate = true;
      controls.autoRotateSpeed = 0.4;
    }
  }, [graphData]);

  // Graph data for ForceGraph3D
  const forceGraphData = useMemo(() => {
    if (!graphData) return { nodes: [], links: [] };
    return {
      nodes: graphData.nodes.map((n) => ({ ...n })),
      links: graphData.links.map((l) => ({ ...l })),
    };
  }, [graphData]);

  const getNodeOpacity = useCallback(
    (node: GraphNode) => {
      if (!hasHighlight) return 0.9;
      return highlightedNodes.has(node.id) ? 1.0 : 0.08;
    },
    [hasHighlight, highlightedNodes]
  );

  const getLinkOpacity = useCallback(
    (link: GraphLink) => {
      if (!hasHighlight) return 0.2;
      const sourceId =
        typeof link.source === "string" ? link.source : link.source.id;
      const targetId =
        typeof link.target === "string" ? link.target : link.target.id;
      const linkId = `${sourceId}-${link.type}-${targetId}`;
      return highlightedLinks.has(linkId) ? 0.6 : 0.03;
    },
    [hasHighlight, highlightedLinks]
  );

  const isLinkHighlighted = useCallback(
    (link: GraphLink) => {
      if (!hasHighlight) return false;
      const sourceId =
        typeof link.source === "string" ? link.source : link.source.id;
      const targetId =
        typeof link.target === "string" ? link.target : link.target.id;
      const linkId = `${sourceId}-${link.type}-${targetId}`;
      return highlightedLinks.has(linkId);
    },
    [hasHighlight, highlightedLinks]
  );

  const nodeThreeObject = useCallback(
    (node: GraphNode) => {
      const group = new THREE.Group();
      const size = nodeSizes[node.label] ?? DEFAULT_NODE_SIZE;
      const color = nodeColors[node.label] ?? DEFAULT_NODE_COLOR;

      // Sphere
      const geometry = new THREE.SphereGeometry(size, 16, 12);
      const material = new THREE.MeshLambertMaterial({
        color,
        transparent: true,
        opacity: getNodeOpacity(node),
      });
      const sphere = new THREE.Mesh(geometry, material);
      group.add(sphere);

      // Glow (subtle emissive ring for highlighted nodes)
      if (hasHighlight && highlightedNodes.has(node.id)) {
        const glowGeo = new THREE.SphereGeometry(size * 1.6, 16, 12);
        const glowMat = new THREE.MeshBasicMaterial({
          color,
          transparent: true,
          opacity: 0.15,
        });
        const glow = new THREE.Mesh(glowGeo, glowMat);
        group.add(glow);
      }

      // Label sprite
      const sprite = new SpriteText(node.name || node.id);
      sprite.color = color;
      sprite.textHeight = 2;
      sprite.position.set(0, size + 2, 0);
      sprite.material.depthWrite = false;
      sprite.visible = false; // toggled by distance check in onEngineTick
      sprite.name = "label";
      group.add(sprite);

      return group;
    },
    [getNodeOpacity, hasHighlight, highlightedNodes]
  );

  const handleNodeClick = useCallback(
    (node: GraphNode) => {
      setSelectedNode(node);
    },
    [setSelectedNode]
  );

  const handleLinkClick = useCallback(
    (link: GraphLink) => {
      setSelectedLink(link);
    },
    [setSelectedLink]
  );

  const handleEngineTick = useCallback(() => {
    const fg = graphRef.current;
    if (!fg) return;

    const camera = fg.camera();
    if (!camera) return;

    const cameraPos = camera.position;

    // Toggle label visibility based on distance to camera
    const scene = fg.scene();
    if (!scene) return;

    scene.traverse((obj: THREE.Object3D) => {
      if (obj.name === "label" && obj.parent) {
        const worldPos = new THREE.Vector3();
        obj.parent.getWorldPosition(worldPos);
        const dist = cameraPos.distanceTo(worldPos);
        obj.visible = dist < LABEL_VISIBLE_DISTANCE;
      }
    });
  }, []);

  const handleBackgroundClick = useCallback(() => {
    setSelectedNode(null);
    setSelectedLink(null);
  }, [setSelectedNode, setSelectedLink]);

  if (!graphData) {
    return (
      <div className="flex items-center justify-center h-screen w-full">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-slate-400 tracking-wide">
            Loading knowledge graph...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="absolute inset-0 transition-[width] duration-500 ease-in-out"
      style={{
        width: sidebarOpen ? "calc(100% - 420px)" : "100%",
      }}
    >
      <ForceGraph3D
        ref={graphRef}
        graphData={forceGraphData}
        nodeId="id"
        nodeLabel=""
        nodeThreeObject={nodeThreeObject}
        nodeThreeObjectExtend={false}
        linkSource="source"
        linkTarget="target"
        linkColor={(link: GraphLink) =>
          `rgba(255,255,255,${getLinkOpacity(link)})`
        }
        linkWidth={(link: GraphLink) =>
          isLinkHighlighted(link) ? 1.5 : 0.3
        }
        linkDirectionalParticles={(link: GraphLink) =>
          isLinkHighlighted(link) ? 2 : 0
        }
        linkDirectionalParticleWidth={1.5}
        linkDirectionalParticleColor={() => "#818cf8"}
        linkOpacity={1}
        backgroundColor="#000011"
        onNodeClick={handleNodeClick}
        onLinkClick={handleLinkClick}
        onBackgroundClick={handleBackgroundClick}
        onEngineTick={handleEngineTick}
        warmupTicks={100}
        cooldownTicks={200}
        enableNodeDrag={true}
        enableNavigationControls={true}
      />
    </div>
  );
}
