import { useState } from "react";
import { ThemeProvider } from "./components/ThemeContext";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { Chat } from "./Chat";
import { Documents } from "./Documents";

export function App() {
  const [tab, setTab] = useState<"chat" | "documents">("chat");

  return (
    <ThemeProvider>
      <div className="app-layout">
        <Header activeTab={tab} />
        <div className="app-body">
          <Sidebar activeTab={tab} setTab={setTab} />
          <main className="main-content">
            {tab === "chat" ? <Chat /> : <Documents />}
          </main>
        </div>
      </div>
    </ThemeProvider>
  );
}
