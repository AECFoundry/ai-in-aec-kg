import { useEffect } from "react";
import { useAppStore } from "./stores/appStore";
import { useChat } from "./hooks/useChat";
import LeftSidebar from "./components/LeftSidebar";
import GraphCanvas from "./components/GraphCanvas";
import ChatSidebar from "./components/ChatSidebar";
import ChatInput from "./components/ChatInput";
import NodePopover from "./components/NodePopover";

export default function App() {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const graphData = useAppStore((s) => s.graphData);
  const theme = useAppStore((s) => s.theme);
  const { sendMessage } = useChat();

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-canvas">
      {/* Left sidebar — node/relationship browser */}
      <LeftSidebar />

      {/* 3D Force Graph */}
      <GraphCanvas />

      {/* Floating chat input (centered in graph area when chat sidebar is closed) */}
      {!sidebarOpen && graphData && (
        <div
          className="fixed bottom-8 z-30"
          style={{ left: "320px", width: "calc(100% - 320px)" }}
        >
          <div className="flex justify-center px-4">
            <div className="relative w-full max-w-xl">
              <div className="absolute inset-0 -z-10 rounded-2xl bg-indigo-500/5 blur-xl" />
              <ChatInput onSubmit={sendMessage} />
            </div>
          </div>
        </div>
      )}

      {/* Chat Sidebar */}
      <ChatSidebar />

      {/* Node/Link Popover */}
      <NodePopover />
    </div>
  );
}
