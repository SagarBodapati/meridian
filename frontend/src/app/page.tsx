import { Sidebar } from "@/components/Sidebar";
import { ChatWindow } from "@/components/Chat/ChatWindow";

export default function Home() {
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar />
      <main className="flex-1 flex flex-col overflow-hidden">
        <ChatWindow />
      </main>
    </div>
  );
}
