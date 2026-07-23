import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { streamChat } from "./sse";
import { fetchSessionMessages, sendFeedback } from "./api";
import { Source } from "./types";
import { CitationDrawer, CitationData } from "./components/CitationDrawer";

interface Message {
  id?: number;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  streaming?: boolean;
}


const PROMPT_SUGGESTIONS = [
  "What are the key findings in the uploaded documents?",
  "Summarize technical architecture and chunking logic",
  "Search vector database for configuration settings",
];

const Markdown = React.memo(function Markdown({ content }: { content: string }) {
  return <ReactMarkdown>{content}</ReactMarkdown>;
});

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<CitationData | null>(null);
  const sessionRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    const stored = localStorage.getItem("rag_session_id");
    if (!stored) return;
    const id = Number(stored);
    if (!Number.isFinite(id) || id <= 0) return;
    sessionRef.current = id;
    fetchSessionMessages(id)
      .then((msgs) => {
        setMessages(
          msgs.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            sources: m.sources ?? [],
            streaming: false,
          })),
        );

      })
      .catch(() => {});
  }, []);

  async function send(queryOverride?: string) {
    const question = (queryOverride ?? input).trim();
    if (!question || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [
      ...m,
      { role: "user", content: question, sources: [] },
      { role: "assistant", content: "", sources: [], streaming: true },
    ]);

    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    try {
      await streamChat(
        question,
        sessionRef.current,
        (e) => {
          if (e.type === "session") {
            sessionRef.current = e.session_id;
            localStorage.setItem("rag_session_id", String(e.session_id));
          } else if (e.type === "token") {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = {
                ...copy[copy.length - 1],
                content: copy[copy.length - 1].content + e.content,
              };
              return copy;
            });
          } else if (e.type === "sources") {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = {
                ...copy[copy.length - 1],
                sources: e.sources,
              };
              return copy;
            });
          } else if (e.type === "done") {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = {
                ...copy[copy.length - 1],
                streaming: false,
              };
              return copy;
            });
          }
        },
        (err) => {
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = {
              role: "assistant",
              content: `Error: ${err.message}`,
              sources: [],
              streaming: false,
            };
            return copy;
          });
        },
        ac.signal,
      );
    } finally {
      setBusy(false);
      setMessages((m) => {
        const copy = [...m];
        const last = copy[copy.length - 1];
        if (last && last.role === "assistant")
          copy[copy.length - 1] = { ...last, streaming: false };
        return copy;
      });
    }
  }

  function handleChipClick(promptText: string) {
    if (busy) return;
    setInput(promptText);
    send(promptText);
  }

  return (
    <div className="chat-container">
      <div className="chat">
        <div className="messages" aria-live="polite" aria-label="Chat messages">
          {messages.length === 0 ? (
            <div className="welcome-hero">
              <h2>Welcome to RAG Studio</h2>
              <p>Ask questions about your uploaded documents or select a prompt below to get started:</p>
              <div className="prompt-chips">
                {PROMPT_SUGGESTIONS.map((promptText, idx) => (
                  <button
                    key={idx}
                    className="prompt-chip"
                    onClick={() => handleChipClick(promptText)}
                  >
                    {promptText}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                {m.role === "assistant" ? (
                  <Markdown content={m.content || (m.streaming ? "…" : "")} />
                ) : (
                  <p>{m.content}</p>
                )}
                {m.role === "assistant" && m.sources && m.sources.length > 0 && (
                  <div className="sources">
                    {m.sources.map((s, j) => (
                      <button
                        key={j}
                        className="citation-pill"
                        onClick={() =>
                          setSelectedCitation({
                            filename: s.filename,
                            chunkId: s.chunk_id || `${s.filename}-p${s.page}`,
                            text: s.text,
                            score: s.score,
                          })
                        }
                      >
                        [{j + 1}] {s.filename} p.{s.page}
                      </button>
                    ))}
                  </div>
                )}
                {m.role === "assistant" && m.id != null && (
                  <div className="feedback-row">
                    <button className="fb-btn" aria-label="Helpful" onClick={() => sendFeedback(m.id!, 1).catch(() => {})}>👍</button>
                    <button className="fb-btn" aria-label="Not helpful" onClick={() => sendFeedback(m.id!, -1).catch(() => {})}>👎</button>
                  </div>
                )}
              </div>

            ))
          )}
        </div>
        <div className="composer">
          <input
            placeholder="Ask about the manuals…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") send();
            }}
            disabled={busy}
          />
          <button onClick={() => send()} disabled={busy}>
            Send
          </button>
        </div>
      </div>
      <CitationDrawer
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
    </div>
  );
}

