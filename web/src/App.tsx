import { useState } from "react";
import { ThemeProvider } from "./components/ThemeContext";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { Chat } from "./Chat";
import { Documents } from "./Documents";

export function App() {
  const [tab, setTab] = useState<"chat" | "documents">("chat");
  const [chatKey, setChatKey] = useState(0);

  return (
    <ThemeProvider>
      <div className="app-layout">
        <Header activeTab={tab} />
        <div className="app-body">
          <Sidebar activeTab={tab} setTab={setTab} onNewChat={() => setChatKey((k) => k + 1)} />
          <main className="main-content">
            {tab === "chat" ? <Chat key={chatKey} /> : <Documents />}
          </main>
        </div>
      </div>
    </ThemeProvider>
  );
}
