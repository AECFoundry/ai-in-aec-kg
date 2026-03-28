import { useRef, useState, useCallback, useEffect, useMemo } from "react";
import ForceGraph3D from "react-force-graph-3d";
import * as THREE from "three";
import { useAppStore } from "../stores/appStore";
import { useGraphData } from "../hooks/useGraphData";
import { nodeColors, nodeSizes } from "../styles/theme";
import type { GraphNode, GraphLink } from "../lib/types";

const DEFAULT_NODE_COLOR = "#8b5cf6";
const LEFT_SIDEBAR_WIDTH = 320;
const RIGHT_SIDEBAR_WIDTH = 420;

export default function GraphCanvas() {
  const graphRef = useRef<any>(null); // eslint-disable-line @typescript-eslint/no-explicit-any
  const containerRef = useRef<HTMLDivElement>(null);
  const nodeObjectsRef = useRef(new Map<string, THREE.Group>());
  const linkObjectsRef = useRef(new Map<string, THREE.Group>());

  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const setSelectedNode = useAppStore((s) => s.setSelectedNode);
  const setSelectedLink = useAppStore((s) => s.setSelectedLink);
  const highlightedNodes = useAppStore((s) => s.highlightedNodes);
  const highlightedLinks = useAppStore((s) => s.highlightedLinks);
  const flyToNodeId = useAppStore((s) => s.flyToNodeId);
  const setFlyToNodeId = useAppStore((s) => s.setFlyToNodeId);
  const focusNode = useAppStore((s) => s.focusNode);
  const clearHighlight = useAppStore((s) => s.clearHighlight);
  const graphData = useGraphData();

  const hasHighlight = highlightedNodes.size > 0;

  // Explicit dimensions
  const [dimensions, setDimensions] = useState({
    width: window.innerWidth - LEFT_SIDEBAR_WIDTH,
    height: window.innerHeight,
  });

  useEffect(() => {
    const onResize = () => {
      const el = containerRef.current;
      if (el) {
        setDimensions({ width: el.clientWidth, height: el.clientHeight });
      } else {
        const rightW = sidebarOpen ? RIGHT_SIDEBAR_WIDTH : 0;
        setDimensions({
          width: window.innerWidth - LEFT_SIDEBAR_WIDTH - rightW,
          height: window.innerHeight,
        });
      }
    };
    window.addEventListener("resize", onResize);
    onResize();
    return () => window.removeEventListener("resize", onResize);
  }, [sidebarOpen]);

  // Auto-rotation + scene setup
  useEffect(() => {
    const fg = graphRef.current;
    if (!fg) return;
    const controls = fg.controls?.();
    if (controls) {
      controls.autoRotate = true;
      controls.autoRotateSpeed = 0.4;
    }
    const scene = fg.scene?.();
    if (scene) {
      const ambient = new THREE.AmbientLight(0x404060, 1.5);
      ambient.name = "custom-ambient";
      if (!scene.getObjectByName("custom-ambient")) {
        scene.add(ambient);
      }
    }
  }, [graphData]);

  // Pause auto-rotation when highlighting is active
  useEffect(() => {
    const fg = graphRef.current;
    if (!fg) return;
    const controls = fg.controls?.();
    if (controls) {
      controls.autoRotate = !hasHighlight;
    }
  }, [hasHighlight]);

  // Strip heavy properties for force graph
  const forceGraphData = useMemo(() => {
    if (!graphData) return { nodes: [], links: [] };
    return {
      nodes: graphData.nodes.map((n) => ({
        id: n.id,
        label: n.label,
        name: n.name,
        group: n.group,
        properties: {},
      })),
      links: graphData.links.map((l) => ({
        source: typeof l.source === "string" ? l.source : l.source.id,
        target: typeof l.target === "string" ? l.target : l.target.id,
        type: l.type,
        properties: {},
      })),
    };
  }, [graphData]);

  // Custom node object with cached THREE groups
  const nodeThreeObject = useCallback((node: GraphNode) => {
    const existing = nodeObjectsRef.current.get(node.id);
    if (existing) return existing;

    const size = nodeSizes[node.label] ?? 3;
    const color = nodeColors[node.label] ?? DEFAULT_NODE_COLOR;

    const group = new THREE.Group();

    // Main sphere
    const geo = new THREE.SphereGeometry(size, 16, 12);
    const mat = new THREE.MeshLambertMaterial({
      color,
      transparent: true,
      opacity: 0.9,
    });
    const sphere = new THREE.Mesh(geo, mat);
    sphere.name = "sphere";
    group.add(sphere);

    // Glow sphere (hidden initially)
    const glowGeo = new THREE.SphereGeometry(size * 1.8, 16, 12);
    const glowMat = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0,
    });
    const glow = new THREE.Mesh(glowGeo, glowMat);
    glow.name = "glow";
    group.add(glow);

    nodeObjectsRef.current.set(node.id, group);
    return group;
  }, []);

  // Reactively update node materials when highlights change
  useEffect(() => {
    nodeObjectsRef.current.forEach((group, nodeId) => {
      const isHl = highlightedNodes.has(nodeId);
      const sphereOpacity = hasHighlight ? (isHl ? 1.0 : 0.08) : 0.9;
      const glowOpacity = hasHighlight && isHl ? 0.15 : 0;

      group.children.forEach((child) => {
        const mesh = child as THREE.Mesh;
        if (mesh.name === "sphere" && mesh.material) {
          (mesh.material as THREE.MeshLambertMaterial).opacity = sphereOpacity;
        }
        if (mesh.name === "glow" && mesh.material) {
          (mesh.material as THREE.MeshBasicMaterial).opacity = glowOpacity;
        }
      });
    });
  }, [highlightedNodes, hasHighlight]);

  // Custom link object with ref caching
  const linkThreeObject = useCallback((link: GraphLink) => {
    const sourceId =
      typeof link.source === "string" ? link.source : link.source.id;
    const targetId =
      typeof link.target === "string" ? link.target : link.target.id;
    const linkKey = `${sourceId}->${targetId}`;

    const group = new THREE.Group();

    // Outer glow
    const glowMat = new THREE.MeshBasicMaterial({
      color: 0x8b9cf8,
      transparent: true,
      opacity: 0.12,
    });
    const glowGeo = new THREE.CylinderGeometry(0.6, 0.6, 1, 4);
    glowGeo.rotateX(Math.PI / 2);
    glowGeo.translate(0, 0, 0.5);
    const glowMesh = new THREE.Mesh(glowGeo, glowMat);
    glowMesh.name = "glow";
    group.add(glowMesh);

    // Core line
    const coreMat = new THREE.MeshBasicMaterial({
      color: 0xa5b4fc,
      transparent: true,
      opacity: 0.45,
    });
    const coreGeo = new THREE.CylinderGeometry(0.12, 0.12, 1, 4);
    coreGeo.rotateX(Math.PI / 2);
    coreGeo.translate(0, 0, 0.5);
    const coreMesh = new THREE.Mesh(coreGeo, coreMat);
    coreMesh.name = "core";
    group.add(coreMesh);

    linkObjectsRef.current.set(linkKey, group);
    return group;
  }, []);

  // Reactively update link materials when highlights change
  useEffect(() => {
    linkObjectsRef.current.forEach((group, linkKey) => {
      const isHl = highlightedLinks.has(linkKey);
      // Also highlight links connecting two highlighted nodes
      const [sourceId, targetId] = linkKey.split("->");
      const connectsHighlighted =
        hasHighlight &&
        highlightedNodes.has(sourceId) &&
        highlightedNodes.has(targetId);
      const shouldHighlight = isHl || connectsHighlighted;

      group.children.forEach((child) => {
        const mesh = child as THREE.Mesh;
        if (mesh.name === "glow") {
          (mesh.material as THREE.MeshBasicMaterial).opacity = hasHighlight
            ? shouldHighlight
              ? 0.25
              : 0.03
            : 0.12;
        }
        if (mesh.name === "core") {
          (mesh.material as THREE.MeshBasicMaterial).opacity = hasHighlight
            ? shouldHighlight
              ? 0.85
              : 0.06
            : 0.45;
        }
      });
    });
  }, [highlightedLinks, highlightedNodes, hasHighlight]);

  // Position custom link objects between source and target
  const linkPositionUpdate = useCallback(
    (
      group: THREE.Object3D,
      coords: {
        start: { x: number; y: number; z: number };
        end: { x: number; y: number; z: number };
      }
    ) => {
      const { start, end } = coords;
      const dx = end.x - start.x;
      const dy = end.y - start.y;
      const dz = end.z - start.z;
      const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1;

      group.position.set(start.x, start.y, start.z);
      group.lookAt(end.x, end.y, end.z);
      group.children.forEach((child) => {
        child.scale.set(1, 1, dist);
      });

      return true;
    },
    []
  );

  // Camera fly-to effect
  useEffect(() => {
    if (!flyToNodeId) return;
    const fg = graphRef.current;
    if (!fg) return;

    // Find node position from ForceGraph's mutated data
    const nodeData = forceGraphData.nodes.find(
      (n) => n.id === flyToNodeId
    ) as any;
    if (!nodeData || nodeData.x === undefined) {
      setFlyToNodeId(null);
      return;
    }

    const distance = 180;
    const pos = { x: nodeData.x, y: nodeData.y, z: nodeData.z };
    const hypot = Math.hypot(pos.x, pos.y, pos.z) || 1;
    const distRatio = 1 + distance / hypot;

    fg.cameraPosition(
      { x: pos.x * distRatio, y: pos.y * distRatio, z: pos.z * distRatio },
      pos,
      1500
    );

    setFlyToNodeId(null);
  }, [flyToNodeId, forceGraphData.nodes, setFlyToNodeId]);

  const handleNodeClick = useCallback(
    (node: GraphNode) => {
      // Toggle: clicking an already-focused node deselects it
      if (highlightedNodes.size === 1 && highlightedNodes.has(node.id)) {
        setSelectedNode(null);
        clearHighlight();
        return;
      }
      const fullNode = graphData?.nodes.find((n) => n.id === node.id);
      if (fullNode) {
        // Navigate first, show card after camera arrives
        focusNode(fullNode.id);
        setTimeout(() => setSelectedNode(fullNode), 1500);
      }
    },
    [setSelectedNode, graphData, focusNode, clearHighlight, highlightedNodes]
  );

  const handleLinkClick = useCallback(
    (link: GraphLink) => {
      setSelectedLink(link);
    },
    [setSelectedLink]
  );

  const handleBackgroundClick = useCallback(() => {
    setSelectedNode(null);
    setSelectedLink(null);
    clearHighlight();
  }, [setSelectedNode, setSelectedLink, clearHighlight]);

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
      ref={containerRef}
      className="absolute inset-0"
      style={{
        left: `${LEFT_SIDEBAR_WIDTH}px`,
        width: sidebarOpen
          ? `calc(100% - ${LEFT_SIDEBAR_WIDTH}px - ${RIGHT_SIDEBAR_WIDTH}px)`
          : `calc(100% - ${LEFT_SIDEBAR_WIDTH}px)`,
        background:
          "radial-gradient(ellipse at 50% 50%, #0a0f2e 0%, #060b1f 40%, #020510 100%)",
      }}
    >
      <ForceGraph3D
        ref={graphRef}
        graphData={forceGraphData}
        width={dimensions.width}
        height={dimensions.height}
        nodeId="id"
        nodeLabel="name"
        nodeThreeObject={nodeThreeObject}
        nodeThreeObjectExtend={false}
        linkSource="source"
        linkTarget="target"
        linkThreeObject={linkThreeObject}
        linkThreeObjectExtend={false}
        linkPositionUpdate={linkPositionUpdate}
        backgroundColor="rgba(0,0,0,0)"
        onNodeClick={handleNodeClick}
        onLinkClick={handleLinkClick}
        onBackgroundClick={handleBackgroundClick}
        warmupTicks={100}
        cooldownTicks={300}
      />
    </div>
  );
}
