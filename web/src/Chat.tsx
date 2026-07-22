import { useState, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { streamChat } from "./sse";
import { Source } from "./types";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  streaming?: boolean;
}

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const sessionRef = useRef<number | null>(null);

  async function send() {
    const question = input.trim();
    if (!question || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", content: question, sources: [] }, { role: "assistant", content: "", sources: [], streaming: true }]);

    await streamChat(
      question,
      sessionRef.current,
      (e) => {
        if (e.type === "session") { sessionRef.current = e.session_id; }
        else if (e.type === "token") {
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { ...copy[copy.length - 1], content: copy[copy.length - 1].content + e.content };
            return copy;
          });
        } else if (e.type === "sources") {
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { ...copy[copy.length - 1], sources: e.sources };
            return copy;
          });
        } else if (e.type === "done") {
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { ...copy[copy.length - 1], streaming: false };
            return copy;
          });
        }
      },
      (err) => {
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = { role: "assistant", content: `Error: ${err.message}`, sources: [], streaming: false };
          return copy;
        });
      },
    );
    setBusy(false);
  }

  return (
    <div className="chat">
      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.role === "assistant" ? <ReactMarkdown>{m.content || (m.streaming ? "…" : "")}</ReactMarkdown> : <p>{m.content}</p>}
            {m.sources.length > 0 && (
              <div className="sources">
                {m.sources.map((s, j) => <SourceChip key={j} source={s} />)}
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="composer">
        <input
          placeholder="Ask about the manuals…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") send(); }}
          disabled={busy}
        />
        <button onClick={send} disabled={busy}>Send</button>
      </div>
    </div>
  );
}

function SourceChip({ source }: { source: Source }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="chip">
      <button className="chip-btn" onClick={() => setOpen((o) => !o)}>{source.filename} p.{source.page}</button>
      {open && <span className="chip-text">{source.text}</span>}
    </span>
  );
}
