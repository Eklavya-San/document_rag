# Plan 4 — Frontend (React Chat UI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Vite + React + TypeScript SPA with two screens — **Chat** (streaming answers + source citations) and **Documents** (upload + ingestion status + delete) — served by the `web` container via a multi-stage Node→nginx build that proxies the API routes.

**Architecture:** A React SPA calls the existing backend with **relative URLs** (`/chat`, `/documents`, `/health`). In dev, Vite proxies those to `http://localhost:8000`. In production, nginx serves the built SPA and proxies `/chat`, `/documents`, `/health` to `http://api:8000` (with SSE buffering off for `/chat`). Chat uses `fetch` + `ReadableStream` to consume the SSE event protocol (`session`/`token`/`sources`/`done`) — `EventSource` can't be used because `/chat` is POST with a JSON body.

**Tech Stack:** Vite 5, React 18, TypeScript 5, react-markdown, Vitest + @testing-library/react (jsdom), Docker (node:20-alpine build → nginx:alpine serve).

## Global Constraints

- The SPA calls the API with **relative URLs only** (no absolute origin) so dev (Vite proxy) and prod (nginx proxy) both work single-origin.
- The `/chat` SSE stream has no `event:` field — dispatch on the JSON `type` inside each `data: {...}` line. Treat a missing `done` event as a transport error.
- No auth / no login (v1). Two screens: Chat and Documents.
- Tests run locally with `npm test` (Vitest, jsdom). The production build runs inside the Docker multi-stage build (no local Node required for the Docker smoke test, but Node IS available locally).
- The `web` Dockerfile becomes a multi-stage build (node:20-alpine → nginx:alpine) replacing the Plan 1 stub. `nginx.conf` proxies API routes.
- Source citations show `filename` + `page` (clickable to reveal the `text` snippet).
- Document status polling continues while any document is in `pending`/`parsing`/`embedding`.
- Deferred (noted, not built): Playwright browser smoke test (needs browser install — manual browser check instead); auth; real reranker/language/section (backend polish plan).

## File Structure (this plan)

```
web/
  package.json              # NEW
  vite.config.ts            # NEW (dev proxy + vitest config)
  tsconfig.json             # NEW
  tsconfig.node.json        # NEW
  index.html                # NEW (replaces Plan 1 stub)
  nginx.conf                # NEW
  Dockerfile                # REPLACE (multi-stage)
  src/
    main.tsx                # NEW
    setupTests.ts           # NEW
    App.tsx                 # NEW (tab switch)
    types.ts                # NEW (shared types)
    api.ts                  # NEW (fetch helpers)
    sse.ts                  # NEW (SSE parser + streamChat)
    Chat.tsx                # NEW
    Documents.tsx           # NEW
    styles.css              # NEW
  src/api.test.ts           # NEW
  src/sse.test.ts           # NEW
  src/Chat.test.tsx         # NEW
  src/Documents.test.tsx    # NEW
docker-compose.yml          # MODIFY (web service uses multi-stage build; ports 8080:80)
```

---

### Task 1: Scaffold the Vite + React + TS app + Docker/nginx

**Files:**
- Create: `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/tsconfig.node.json`, `web/index.html`, `web/src/main.tsx`, `web/src/App.tsx`, `web/src/styles.css`, `web/src/setupTests.ts`
- Replace: `web/Dockerfile` (multi-stage), `web/index.html` (replaces stub)
- Create: `web/nginx.conf`
- Modify: `docker-compose.yml` (web service)
- Create: `web/.gitignore` (node_modules, dist)

**Interfaces:**
- Produces: a Vite app that `npm install && npm run build` builds to `web/dist`, served by nginx in Docker, proxying API routes. `App` renders a tab bar (Chat / Documents) — the screen components are stubs in this task, filled in Tasks 4–5.

- [ ] **Step 1: Create `web/package.json`**

```json
{
  "name": "manual-rag-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "react-markdown": "9.0.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "6.4.6",
    "@testing-library/react": "16.0.0",
    "@testing-library/user-event": "14.5.2",
    "@types/react": "18.3.3",
    "@types/react-dom": "18.3.0",
    "@vitejs/plugin-react": "4.3.1",
    "jsdom": "24.1.0",
    "typescript": "5.5.3",
    "vite": "5.3.1",
    "vitest": "1.6.0"
  }
}
```

- [ ] **Step 2: Create `web/vite.config.ts`**

```ts
/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/chat": "http://localhost:8000",
      "/documents": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.ts",
  },
});
```

- [ ] **Step 3: Create `web/tsconfig.json` and `web/tsconfig.node.json`**

`web/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

`web/tsconfig.node.json`:
```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Create `web/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Manual Assistant</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create `web/src/main.tsx`, `web/src/App.tsx`, `web/src/styles.css`, `web/src/setupTests.ts`**

`web/src/main.tsx`:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

`web/src/App.tsx` (stubs for Chat/Documents filled in Tasks 4–5):
```tsx
import { useState } from "react";

export function App() {
  const [tab, setTab] = useState<"chat" | "documents">("chat");
  return (
    <div className="app">
      <header className="tabs">
        <button className={tab === "chat" ? "active" : ""} onClick={() => setTab("chat")}>Chat</button>
        <button className={tab === "documents" ? "active" : ""} onClick={() => setTab("documents")}>Documents</button>
      </header>
      <main>
        {tab === "chat" ? <div data-testid="chat-placeholder">Chat</div> : <div data-testid="documents-placeholder">Documents</div>}
      </main>
    </div>
  );
}
```

`web/src/styles.css`:
```css
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, sans-serif; }
.app { max-width: 900px; margin: 0 auto; padding: 1rem; }
.tabs button { padding: 0.5rem 1rem; margin-right: 0.5rem; cursor: pointer; }
.tabs button.active { font-weight: bold; border-bottom: 2px solid #333; }
```

`web/src/setupTests.ts`:
```ts
import "@testing-library/jest-dom";
```

- [ ] **Step 6: Create `web/.gitignore`**

```
node_modules/
dist/
```

- [ ] **Step 7: Create `web/nginx.conf`**

```
server {
  listen 80;
  server_name _;

  location / {
    root /usr/share/nginx/html;
    try_files $uri $uri/ /index.html;
  }

  location /health {
    proxy_pass http://api:8000;
  }

  location /documents {
    proxy_pass http://api:8000;
    client_max_body_size 100m;
  }

  location /chat {
    proxy_pass http://api:8000;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 3600s;
    chunked_transfer_encoding on;
  }
}
```

- [ ] **Step 8: Replace `web/Dockerfile` with a multi-stage build**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

> Note: `package-lock.json` may not exist yet on first build; the `package-lock.json*` glob with `npm install` (not `npm ci`) handles that. After the first local `npm install` generates a lockfile, it can be committed for reproducible `npm ci`.

- [ ] **Step 9: Update `docker-compose.yml` `web` service**

Change the `web` service to (keep `depends_on: [api]` and `ports: ["8080:80"]`):
```yaml
  web:
    build: ./web
    ports:
      - "8080:80"
    depends_on: [api]
```
(No other service changes.)

- [ ] **Step 10: Install, build, and write a minimal App test**

```
cd /Users/eklavya/youtub3/rag_1/web
npm install
npm run build
```
Expected: `web/dist/index.html` and `web/dist/assets/...` are produced.

Create `web/src/App.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("renders the Chat tab by default", () => {
    render(<App />);
    expect(screen.getByTestId("chat-placeholder")).toBeInTheDocument();
  });

  it("switches to the Documents tab", async () => {
    const { user } = setup();
    await user.click(screen.getByText("Documents"));
    expect(screen.getByTestId("documents-placeholder")).toBeInTheDocument();
  });
});

import userEvent from "@testing-library/user-event";
function setup() {
  const user = userEvent.setup();
  return { user, ...render(<App />) };
}
```

Run: `npm test`
Expected: 2 tests pass.

- [ ] **Step 11: Commit**

```bash
cd /Users/eklavya/youtub3/rag_1
git add web/ docker-compose.yml
git commit -m "feat: scaffold Vite+React+TS app with nginx proxy and multi-stage Docker build"
```

> Note: `web/node_modules/` and `web/dist/` are gitignored. `web/package-lock.json` (if generated) SHOULD be committed for reproducible builds — include it in the `git add` if present.

---

### Task 2: Shared types + API helpers

**Files:**
- Create: `web/src/types.ts`
- Create: `web/src/api.ts`
- Create: `web/src/api.test.ts`

**Interfaces:**
- Produces typed fetch helpers used by the screens:
  - `uploadDocument(file: File) -> Promise<DocumentRow>`
  - `listDocuments() -> Promise<DocumentRow[]>`
  - `deleteDocument(id: number) -> Promise<void>`
  - `fetchSessionMessages(sessionId: number) -> Promise<StoredMessage[]>`
- Types: `DocumentRow { id, filename, status, chunk_count, parser_used, error }`, `Source { filename, page, text, score }`, `StoredMessage { role, content, sources }`.

- [ ] **Step 1: Write the failing test**

`web/src/api.test.ts`:
```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { uploadDocument, listDocuments, deleteDocument, fetchSessionMessages } from "./api";

describe("api helpers", () => {
  beforeEach(() => { (globalThis as any).fetch = vi.fn(); });

  it("uploadDocument POSTs multipart and returns the row", async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: true, json: async () => ({ id: 1, filename: "m.pdf", status: "pending", chunk_count: 0, parser_used: null, error: null }) });
    const row = await uploadDocument(new File(["x"], "m.pdf"));
    expect(row.id).toBe(1);
    const [url, opts] = (globalThis.fetch as any).mock.calls[0];
    expect(url).toBe("/documents/upload");
    expect(opts.method).toBe("POST");
    expect(opts.body).toBeInstanceOf(FormData);
  });

  it("listDocuments GETs /documents", async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: true, json: async () => [{ id: 1, filename: "m.pdf", status: "done", chunk_count: 3, parser_used: "pdf", error: null }] });
    const docs = await listDocuments();
    expect(docs).toHaveLength(1);
    expect((globalThis.fetch as any).mock.calls[0][0]).toBe("/documents");
  });

  it("deleteDocument DELETEs /documents/:id", async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: true, status: 204 });
    await deleteDocument(7);
    const [url, opts] = (globalThis.fetch as any).mock.calls[0];
    expect(url).toBe("/documents/7");
    expect(opts.method).toBe("DELETE");
  });

  it("fetchSessionMessages GETs the session messages", async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: true, json: async () => [{ role: "user", content: "hi", sources: [] }] });
    const msgs = await fetchSessionMessages(5);
    expect(msgs[0].role).toBe("user");
    expect((globalThis.fetch as any).mock.calls[0][0]).toBe("/chat/sessions/5/messages");
  });

  it("throws on a non-ok response", async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: false, status: 503, statusText: "AI service unavailable" });
    await expect(listDocuments()).rejects.toThrow("503");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- src/api.test.ts`
Expected: FAIL — cannot resolve `./api`.

- [ ] **Step 3: Implement `types.ts` and `api.ts`**

`web/src/types.ts`:
```ts
export interface DocumentRow {
  id: number;
  filename: string;
  status: "pending" | "parsing" | "embedding" | "done" | "failed";
  chunk_count: number;
  parser_used: string | null;
  error: string | null;
}

export interface Source {
  filename: string;
  page: number;
  text: string;
  score: number;
}

export interface StoredMessage {
  role: "user" | "assistant";
  content: string;
  sources: Source[];
}
```

`web/src/api.ts`:
```ts
import { DocumentRow, StoredMessage } from "./types";

async function jsonOrThrow<T>(resp: Response): Promise<T> {
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`.trim());
  return resp.json();
}

export async function uploadDocument(file: File): Promise<DocumentRow> {
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch("/documents/upload", { method: "POST", body: form });
  return jsonOrThrow<DocumentRow>(resp);
}

export async function listDocuments(): Promise<DocumentRow[]> {
  const resp = await fetch("/documents");
  return jsonOrThrow<DocumentRow[]>(resp);
}

export async function deleteDocument(id: number): Promise<void> {
  const resp = await fetch(`/documents/${id}`, { method: "DELETE" });
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`.trim());
}

export async function fetchSessionMessages(sessionId: number): Promise<StoredMessage[]> {
  const resp = await fetch(`/chat/sessions/${sessionId}/messages`);
  return jsonOrThrow<StoredMessage[]>(resp);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npm test -- src/api.test.ts` then `npm run build`
Expected: api tests PASS (5); build succeeds.

- [ ] **Step 5: Commit**

```bash
cd /Users/eklavya/youtub3/rag_1
git add web/src/types.ts web/src/api.ts web/src/api.test.ts
git commit -m "feat: typed API helpers for documents and session messages"
```

---

### Task 3: SSE parser + `streamChat`

**Files:**
- Create: `web/src/sse.ts`
- Create: `web/src/sse.test.ts`

**Interfaces:**
- Produces:
  - `ChatEvent` union (`session`/`token`/`sources`/`done`).
  - `parseSseEvents(text: string) -> ChatEvent[]` — split on `\n\n`, parse `data: ` lines as JSON.
  - `async streamChat(question, sessionId, onEvent, onError) -> Promise<void>` — POST `/chat`, read the `ReadableStream`, parse SSE blocks incrementally, call `onEvent` per event. On non-2xx, call `onError`.

- [ ] **Step 1: Write the failing test**

`web/src/sse.test.ts`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { parseSseEvents, streamChat } from "./sse";

describe("parseSseEvents", () => {
  it("parses session/token/sources/done events", () => {
    const text = [
      'data: {"type":"session","session_id":42}',
      "",
      'data: {"type":"token","content":"Hel"}',
      "",
      'data: {"type":"token","content":"lo"}',
      "",
      'data: {"type":"sources","sources":[{"filename":"m.pdf","page":3,"text":"calibrate","score":0.9}]}',
      "",
      'data: {"type":"done"}',
      "",
    ].join("\n");
    const events = parseSseEvents(text);
    expect(events).toHaveLength(5);
    expect(events[0]).toEqual({ type: "session", session_id: 42 });
    expect(events[1]).toEqual({ type: "token", content: "Hel" });
    expect(events[3].type).toBe("sources");
    expect(events[4].type).toBe("done");
  });

  it("ignores non-data lines", () => {
    const text = "event: ping\ndata: {\"type\":\"done\"}\n\n";
    const events = parseSseEvents(text);
    expect(events).toEqual([{ type: "done" }]);
  });
});

describe("streamChat", () => {
  it("calls onEvent for each event from the stream", async () => {
    const encoder = new TextEncoder();
    const chunks = [
      encoder.encode('data: {"type":"session","session_id":1}\n\n'),
      encoder.encode('data: {"type":"token","content":"Hi"}\n\n'),
      encoder.encode('data: {"type":"done"}\n\n'),
    ];
    let i = 0;
    const stream = new ReadableStream({
      pull(controller) { controller.enqueue(chunks[i++]); if (i >= chunks.length) controller.close(); },
    });
    (globalThis as any).fetch = vi.fn().mockResolvedValue({ ok: true, body: stream });

    const events: any[] = [];
    await streamChat("hello", null, (e) => events.push(e), () => {});
    expect(events.map((e) => e.type)).toEqual(["session", "token", "done"]);
    expect((globalThis.fetch as any).mock.calls[0][1].method).toBe("POST");
  });

  it("calls onError on a non-ok response", async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValue({ ok: false, status: 503, statusText: "AI service unavailable" });
    let err: Error | null = null;
    await streamChat("hello", null, () => {}, (e) => { err = e; });
    expect(err).not.toBeNull();
    expect(err!.message).toContain("503");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- src/sse.test.ts`
Expected: FAIL — cannot resolve `./sse`.

- [ ] **Step 3: Implement `sse.ts`**

```ts
import { Source } from "./types";

export type ChatEvent =
  | { type: "session"; session_id: number }
  | { type: "token"; content: string }
  | { type: "sources"; sources: Source[] }
  | { type: "done" };

export function parseSseEvents(text: string): ChatEvent[] {
  const events: ChatEvent[] = [];
  for (const block of text.split("\n\n")) {
    for (const line of block.split("\n")) {
      if (line.startsWith("data: ")) {
        events.push(JSON.parse(line.slice(6)) as ChatEvent);
      }
    }
  }
  return events;
}

export async function streamChat(
  question: string,
  sessionId: number | null,
  onEvent: (e: ChatEvent) => void,
  onError: (err: Error) => void,
): Promise<void> {
  let resp: Response;
  try {
    resp = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, session_id: sessionId }),
    });
  } catch (e) {
    onError(e as Error);
    return;
  }
  if (!resp.ok || !resp.body) {
    onError(new Error(`${resp.status} ${resp.statusText}`.trim()));
    return;
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      for (const line of block.split("\n")) {
        if (line.startsWith("data: ")) {
          onEvent(JSON.parse(line.slice(6)) as ChatEvent);
        }
      }
    }
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npm test -- src/sse.test.ts` then `npm run build`
Expected: sse tests PASS (4); build succeeds.

- [ ] **Step 5: Commit**

```bash
cd /Users/eklavya/youtub3/rag_1
git add web/src/sse.ts web/src/sse.test.ts
git commit -m "feat: SSE parser and streamChat consumer for /chat"
```

---

### Task 4: Chat screen

**Files:**
- Create: `web/src/Chat.tsx`
- Create: `web/src/Chat.test.tsx`
- Modify: `web/src/App.tsx` (render `<Chat />` instead of the placeholder)

**Interfaces:**
- Consumes: `streamChat`, `fetchSessionMessages`, `Source`, `StoredMessage`.
- Produces: a Chat component that lets the user type a question, streams the answer token-by-token, renders the answer as Markdown, and shows source citation chips (filename + page; clicking toggles the snippet text). Maintains a `sessionId` across turns.

- [ ] **Step 1: Write the failing test**

`web/src/Chat.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Chat } from "./Chat";

vi.mock("./sse", () => ({
  streamChat: vi.fn(async (_q: string, _id: number | null, onEvent: (e: any) => void) => {
    onEvent({ type: "session", session_id: 7 });
    onEvent({ type: "token", content: "Hel" });
    onEvent({ type: "token", content: "lo" });
    onEvent({ type: "sources", sources: [{ filename: "m.pdf", page: 3, text: "calibrate the sensor", score: 0.9 }] });
    onEvent({ type: "done" });
  }),
}));

describe("Chat", () => {
  it("streams an answer and shows source chips", async () => {
    const user = userEvent.setup();
    render(<Chat />);
    await user.type(screen.getByPlaceholderText("Ask about the manuals…"), "how to calibrate?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Hello")).toBeInTheDocument();
    expect(await screen.findByText(/m\.pdf.*p\.3/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- src/Chat.test.tsx`
Expected: FAIL — cannot resolve `./Chat`.

- [ ] **Step 3: Implement `Chat.tsx`**

```tsx
import { useState, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { streamChat } from "./sse";
import { fetchSessionMessages } from "./api";
import { Source, StoredMessage } from "./types";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  streaming?: boolean;
}

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<number | null>(null);
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
        if (e.type === "session") { sessionRef.current = e.session_id; setSessionId(e.session_id); }
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
```

- [ ] **Step 4: Wire `<Chat />` into `App.tsx`**

In `web/src/App.tsx`, replace the chat placeholder with the real component:
```tsx
import { Chat } from "./Chat";
...
        {tab === "chat" ? <Chat /> : <div data-testid="documents-placeholder">Documents</div>}
```
(Add the import at the top; keep the Documents placeholder for Task 5.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd web && npm test -- src/Chat.test.tsx` then `npm test` then `npm run build`
Expected: Chat test PASS; full `npm test` green; build succeeds.

- [ ] **Step 6: Commit**

```bash
cd /Users/eklavya/youtub3/rag_1
git add web/src/Chat.tsx web/src/Chat.test.tsx web/src/App.tsx
git commit -m "feat: Chat screen with streaming, markdown, and source chips"
```

---

### Task 5: Documents screen

**Files:**
- Create: `web/src/Documents.tsx`
- Create: `web/src/Documents.test.tsx`
- Modify: `web/src/App.tsx` (render `<Documents />` instead of the placeholder)

**Interfaces:**
- Consumes: `uploadDocument`, `listDocuments`, `deleteDocument`, `DocumentRow`.
- Produces: a Documents component that lists documents with status badges, supports drag-and-drop + button upload, deletes documents, and polls `listDocuments` every 2s while any document is `pending`/`parsing`/`embedding`.

- [ ] **Step 1: Write the failing test**

`web/src/Documents.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Documents } from "./Documents";

vi.mock("./api", () => ({
  uploadDocument: vi.fn().mockResolvedValue({ id: 1, filename: "m.pdf", status: "pending", chunk_count: 0, parser_used: null, error: null }),
  listDocuments: vi.fn().mockResolvedValue([
    { id: 1, filename: "m.pdf", status: "done", chunk_count: 3, parser_used: "pdf", error: null },
    { id: 2, filename: "bad.pdf", status: "failed", chunk_count: 0, parser_used: "pdf", error: "OCR not supported" },
  ]),
  deleteDocument: vi.fn().mockResolvedValue(undefined),
}));

import { uploadDocument, deleteDocument } from "./api";

describe("Documents", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("lists documents with status", async () => {
    render(<Documents />);
    expect(await screen.findByText("m.pdf")).toBeInTheDocument();
    expect(screen.getByText("done")).toBeInTheDocument();
    expect(screen.getByText(/OCR not supported/)).toBeInTheDocument();
  });

  it("uploads a chosen file", async () => {
    const user = userEvent.setup();
    render(<Documents />);
    await screen.findByText("m.pdf");
    const input = screen.getByLabelText("Upload manual") as HTMLInputElement;
    await user.upload(input, new File(["x"], "new.pdf"));
    expect(uploadDocument).toHaveBeenCalled();
  });

  it("deletes a document on click", async () => {
    const user = userEvent.setup();
    render(<Documents />);
    await screen.findByText("m.pdf");
    await user.click(screen.getAllByRole("button", { name: "Delete" })[0]);
    await waitFor(() => expect(deleteDocument).toHaveBeenCalledWith(1));
  });
});
```

> Note: the polling effect calls `listDocuments` on mount and every 2s while any doc is in-flight. With all docs `done`/`failed` in the test, polling stops after the initial load. Use `vi.useFakeTimers()` only if flaky — the test as written waits for the first load via `findByText`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- src/Documents.test.tsx`
Expected: FAIL — cannot resolve `./Documents`.

- [ ] **Step 3: Implement `Documents.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import { uploadDocument, listDocuments, deleteDocument } from "./api";
import { DocumentRow } from "./types";

const INFLIGHT = new Set(["pending", "parsing", "embedding"]);

export function Documents() {
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  async function refresh() {
    try { setDocs(await listDocuments()); } catch { /* ignore transient */ }
  }

  useEffect(() => {
    refresh();
    const id = setInterval(() => {
      if (docs.some((d) => INFLIGHT.has(d.status))) refresh();
    }, 2000);
    return () => clearInterval(id);
  }, [docs]);

  async function handleFiles(files: FileList | null) {
    if (!files) return;
    for (const file of Array.from(files)) {
      try { await uploadDocument(file); } catch { /* ignore */ }
    }
    refresh();
  }

  async function remove(id: number) {
    try { await deleteDocument(id); } catch { /* ignore */ }
    refresh();
  }

  return (
    <div
      className="documents"
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
    >
      <div className={`dropzone ${dragOver ? "over" : ""}`}>
        <p>Drag & drop manuals here, or</p>
        <input ref={fileInput} type="file" multiple accept=".pdf,.docx,.html,.htm" aria-label="Upload manual" onChange={(e) => handleFiles(e.target.files)} />
      </div>
      <ul className="doc-list">
        {docs.map((d) => (
          <li key={d.id} className={`doc ${d.status}`}>
            <span className="doc-name">{d.filename}</span>
            <span className="doc-status">{d.status}{d.chunk_count ? ` (${d.chunk_count} chunks)` : ""}</span>
            {d.error && <span className="doc-error">{d.error}</span>}
            <button onClick={() => remove(d.id)}>Delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

> Note: `aria-label="Upload manual"` on the file input is what makes `getByLabelText("Upload manual")` find it in the test.

- [ ] **Step 4: Wire `<Documents />` into `App.tsx`**

In `web/src/App.tsx`, replace the documents placeholder:
```tsx
import { Chat } from "./Chat";
import { Documents } from "./Documents";
...
        {tab === "chat" ? <Chat /> : <Documents />}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd web && npm test -- src/Documents.test.tsx` then `npm test` then `npm run build`
Expected: Documents test PASS; full `npm test` green; build succeeds.

- [ ] **Step 6: Commit**

```bash
cd /Users/eklavya/youtub3/rag_1
git add web/src/Documents.tsx web/src/Documents.test.tsx web/src/App.tsx
git commit -m "feat: Documents screen with upload, status polling, and delete"
```

---

### Task 6: Integration + Docker smoke test

**Files:**
- No new source files unless the smoke test surfaces a bug.

- [ ] **Step 1: Run the full unit suite + build**

```
cd /Users/eklavya/youtub3/rag_1/web
npm test
npm run build
```
Expected: all Vitest tests pass; `npm run build` produces `web/dist`.

- [ ] **Step 2: Docker smoke test (nginx serves SPA + proxies API)**

```
cd /Users/eklavya/youtub3/rag_1
cp .env.example .env
docker compose up -d --build
sleep 25
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/
curl -s http://localhost:8080/health
curl -s http://localhost:8080/documents
docker compose down
```
Expected:
- `curl http://localhost:8080/` → HTTP `200` and the HTML contains `<div id="root">` (the SPA shell).
- `curl http://localhost:8080/health` → `{"status":"ok",...}` (proxied to api).
- `curl http://localhost:8080/documents` → `[]` (proxied to api).
Record the three outcomes. (A full chat/documents interaction requires a running Ollama + ingested docs; the proxy + SPA served is the smoke gate here. A manual browser check at http://localhost:8080 is the final human verification.)

- [ ] **Step 3: Commit any bug fix surfaced by the smoke test (if none, no commit)**

---

## Self-Review

**1. Spec coverage (Plan 4 scope = frontend):**
- Vite + React + TS SPA → Task 1. ✅
- Chat screen: streaming token rendering, Markdown, source citation chips (filename + page, click → snippet) → Task 4. ✅
- Documents screen: drag-and-drop upload, per-file ingestion status, delete → Task 5. ✅
- SSE consumption (session/token/sources/done) → Task 3. ✅
- No login → all tasks (no auth UI). ✅
- `web` container serves the SPA via nginx + proxies API → Task 1. ✅
- Relative-URL API calls → Tasks 2, 3. ✅
- Document status polling while in-flight → Task 5. ✅
- Deferred: Playwright browser smoke (manual check instead), auth, real reranker/language/section → documented. ✅

**2. Placeholder scan:** No TBD/TODO. The Task 5 `label="Upload manual"` correction is explicit (use `aria-label`). Every test has real assertions. ✅

**3. Type consistency:**
- `DocumentRow`, `Source`, `StoredMessage` defined in `types.ts` (Task 2), used in `api.ts` (Task 2), `sse.ts` (Task 3), `Chat.tsx` (Task 4), `Documents.tsx` (Task 5). ✅
- `ChatEvent` union defined in `sse.ts` (Task 3), produced by `parseSseEvents`/`streamChat` and consumed in `Chat.tsx`. ✅
- `streamChat(question, sessionId, onEvent, onError)` signature consistent across `sse.ts` (Task 3) and `Chat.tsx` (Task 4). ✅
- API helper names (`uploadDocument`/`listDocuments`/`deleteDocument`/`fetchSessionMessages`) consistent across `api.ts` and `Documents.tsx`/`Chat.tsx`. ✅

No issues found.