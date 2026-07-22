import { useState } from "react";
import { Chat } from "./Chat";

export function App() {
  const [tab, setTab] = useState<"chat" | "documents">("chat");
  return (
    <div className="app">
      <header className="tabs">
        <button className={tab === "chat" ? "active" : ""} onClick={() => setTab("chat")}>Chat</button>
        <button className={tab === "documents" ? "active" : ""} onClick={() => setTab("documents")}>Documents</button>
      </header>
      <main>
        {tab === "chat" ? <Chat /> : <div data-testid="documents-placeholder">Documents</div>}
      </main>
    </div>
  );
}
