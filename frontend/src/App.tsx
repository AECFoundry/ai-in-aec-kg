import { useAppStore } from "./stores/appStore";
import { useSession } from "./hooks/useSession";
import { useChat } from "./hooks/useChat";
import GraphCanvas from "./components/GraphCanvas";
import ChatSidebar from "./components/ChatSidebar";
import ChatInput from "./components/ChatInput";
import SignupModal from "./components/SignupModal";
import NodePopover from "./components/NodePopover";

export default function App() {
  useSession();

  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const { sendMessage } = useChat();

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-[#000011]">
      {/* 3D Force Graph */}
      <GraphCanvas />

      {/* Floating chat input at bottom center (visible when sidebar is closed) */}
      {!sidebarOpen && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-30 w-full max-w-xl px-4">
          <div className="relative">
            {/* Subtle glow behind input */}
            <div className="absolute inset-0 -z-10 rounded-2xl bg-indigo-500/5 blur-xl" />
            <ChatInput onSubmit={sendMessage} />
          </div>
          <p className="text-center text-[11px] text-slate-600 mt-3 tracking-wider">
            Explore the AI in AEC conference knowledge graph
          </p>
        </div>
      )}

      {/* Chat Sidebar */}
      <ChatSidebar />

      {/* Signup Modal */}
      <SignupModal />

      {/* Node/Link Popover */}
      <NodePopover />
    </div>
  );
}
