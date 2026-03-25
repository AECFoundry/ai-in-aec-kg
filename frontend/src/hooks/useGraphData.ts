import { useEffect } from "react";
import { fetchGraph } from "../lib/api";
import { useAppStore } from "../stores/appStore";

export function useGraphData() {
  const setGraphData = useAppStore((s) => s.setGraphData);
  const graphData = useAppStore((s) => s.graphData);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await fetchGraph();
        if (!cancelled) {
          setGraphData(data);
        }
      } catch (err) {
        console.error("Failed to fetch graph data:", err);
      }
    }

    if (!graphData) {
      load();
    }

    return () => {
      cancelled = true;
    };
  }, [graphData, setGraphData]);

  return graphData;
}
