import { useAppStore } from "./stores/appStore";
import { useSession } from "./hooks/useSession";
import { useChat } from "./hooks/useChat";
import LeftSidebar from "./components/LeftSidebar";
import GraphCanvas from "./components/GraphCanvas";
import ChatSidebar from "./components/ChatSidebar";
import ChatInput from "./components/ChatInput";
import SignupModal from "./components/SignupModal";
import NodePopover from "./components/NodePopover";
import VoiceOrb from "./components/VoiceOrb";

export default function App() {
  useSession();

  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const graphData = useAppStore((s) => s.graphData);
  const { sendMessage } = useChat();

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-[#060918]">
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
          <p className="text-center text-[11px] text-slate-500 mt-3 tracking-wider">
            Explore the AI in AEC conference knowledge graph
          </p>
        </div>
      )}

      {/* Chat Sidebar */}
      <ChatSidebar />

      {/* Voice Orb */}
      <VoiceOrb />

      {/* Signup Modal */}
      <SignupModal />

      {/* Node/Link Popover */}
      <NodePopover />
    </div>
  );
}
