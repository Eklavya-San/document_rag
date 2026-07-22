# Manual RAG Chatbot — Design

**Date:** 2026-07-22
**Status:** Approved (pending user review of spec)
**Project:** Self-hosted RAG chatbot over a client's library of manuals

## 1. Goal

A web app that lets users ask natural-language questions about a large collection of manuals and get answers grounded strictly in those manuals, with citations back to the source file and page. Fully self-hosted on a Linux machine via Docker; all LLM and embedding inference runs on an external Ollama instance reachable by API URL. No cloud dependencies.

## 2. Requirements

- **Self-hosted:** Docker Compose on Linux. No cloud LLM/embedding APIs.
- **LLM + embeddings via external Ollama** (`OLLAMA_BASE_URL`); Ollama is *not* a service in our compose stack.
- **Multilingual:** manuals and questions may be in multiple languages.
- **Concurrency:** multiple users can chat simultaneously without blocking each other.
- **Mixed document formats:** PDF (text + scanned/OCR), DOCX, HTML — defensive ingestion since the exact mix is unknown.
- **Chat history / follow-ups:** the bot remembers earlier turns within a session.
- **Source citations:** every answer cites the manual + page it came from.
- **Out of scope (v1):** authentication, user management, login. Single shared internal tool. Auth to be added later.

## 3. Architecture

```
┌─────────────┐   HTTP/SSE    ┌──────────────┐   Ollama API   ┌──────────────┐
│  React SPA  │ ────────────▶ │   FastAPI    │ ─────────────▶ │   Ollama     │
│  (Vite+TS)  │               │  (async)     │                │  (external)  │
│  chat UI    │ ◀──────────── │  RAG router  │ ◀───────────── │  LLM + embed │
└─────────────┘   stream      └──────┬───────┘   vectors      └──────────────┘
                                      │
                          ┌───────────┴───────────┐
                          ▼                       ▼
                   ┌─────────────┐         ┌──────────────┐
                   │   Qdrant    │         │  Postgres    │
                   │  vector DB  │         │  metadata +  │
                   │ (multilang) │         │  chat history│
                   └─────────────┘         └──────────────┘
                                      │
                                      ▼
                          ┌───────────────────────┐
                          │  Ingestion pipeline   │
                          │  (LlamaIndex loaders: │
                          │   PDF/DOCX/HTML/OCR)  │
                          │  → chunk → embed →    │
                          │    store in Qdrant    │
                          └───────────────────────┘
```

### Services (docker-compose.yml)

| Service | Role |
|---|---|
| `web` | Vite + React + TypeScript SPA: chat UI + document management |
| `api` | FastAPI async backend: `/chat` (SSE), `/documents` CRUD, ingestion |
| `qdrant` | vector database |
| `postgres` | metadata + chat history |

**External:** Ollama (LLM + embeddings), reached via `OLLAMA_BASE_URL`.

### Key architectural choices

- **SSE streaming** for chat (token-by-token). Simpler than WebSockets; FastAPI handles it cleanly.
- **LlamaIndex** for RAG orchestration (loaders, chunking, retrieval) — avoids reinventing the pipeline.
- **Separation of concerns:** Qdrant holds vectors + chunk payloads; Postgres holds structural metadata + chat history.
- **External Ollama** decouples the app box from the GPU box; they scale independently.

## 4. Components

### 4.1 Frontend (`web/`) — Vite + React + TypeScript

- **Chat screen:** message list with live streaming token rendering, Markdown rendering (manuals contain tables/steps), and **source citation chips** (manual + page, clickable to view the snippet).
- **Documents screen:** drag-and-drop upload, per-file ingestion status (`pending → parsing → embedding → done | failed`), re-trigger, delete. No login (v1).
- SSE stream consumer; no shared state between users (concurrency-ready).

### 4.2 Backend (`api/`) — FastAPI (async Python)

Endpoints:
- `POST /chat` — SSE. Inputs: `question`, `session_id`. Streams LLM tokens; emits a final `sources` event.
- `POST /documents/upload` — multipart upload; creates a `documents` row and kicks off background ingestion.
- `GET /documents` — list with status.
- `GET /documents/{id}` — detail/status.
- `DELETE /documents/{id}` — remove file + its Qdrant points + Postgres rows.

Modules:
- **RAG router:** query embedding → Qdrant top-k search → optional rerank → prompt assembly (system + history + retrieved chunks) → Ollama stream. Isolated so retrieval strategy can be tuned independently of the API layer.
- **Ingestion:** background task that loads a file → parses → chunks → embeds in batches → upserts to Qdrant → updates Postgres. Async so uploads don't block chat.

### 4.3 Models (external Ollama)

- **LLM:** `qwen2.5:32b` (multilingual, fits ~32GB VRAM quantized). Alternative: Command-R 35B.
- **Embeddings:** `bge-m3` (multilingual, ~1024-dim dense vectors, small footprint).

These must be pulled on the external Ollama host (`ollama pull qwen2.5:32b bge-m3`); documented in the README.

### 4.4 Data stores

**Qdrant** — one collection:
- vector: `bge-m3`, 1024-dim, cosine, HNSW index.
- payload per point: `text`, `doc_id`, `filename`, `page`, `section`, `language`.

**Postgres** tables:
- `documents(id, filename, status, chunk_count, parser_used, error, created_at, updated_at)`
- `chat_sessions(id, title, created_at)`
- `chat_messages(id, session_id, role, content, sources_json, created_at)`

Chunk text is stored in Qdrant payloads; Postgres holds only structural metadata to avoid duplication.

### 4.5 Ingestion parsers

- PDF (text-selectable) → PyMuPDF
- DOCX → python-docx
- HTML → BeautifulSoup
- Scanned PDF → automatic OCR fallback (Tesseract or EasyOCR) triggered when a PDF page yields no extractable text; recorded as `parser_used=ocr`.

Tables preserved as structured text where possible.

## 5. Data Flow

### 5.1 Ingestion

```
User drops file in Documents screen
  → POST /documents/upload (multipart)
  → API saves file to /data/manuals/, inserts documents row (status=pending)
  → Background ingestion task:
      1. Detect type → route to parser (PDF/DOCX/HTML/OCR-if-scanned)
      2. Extract text + page/section metadata
      3. Chunk (recursive splitter, ~512 tokens, ~50 overlap; keep page refs)
      4. Embed chunks in batches via Ollama bge-m3
      5. Upsert into Qdrant (payload: text, doc_id, filename, page, language)
      6. Update documents row (status=done, chunk_count=N, parser_used=...)
  → Frontend polls GET /documents/{id} → shows "done" / "failed"
```

### 5.2 Query

```
User types question in Chat
  → POST /chat (question, session_id)  [SSE response]
  → API:
      1. Embed question via bge-m3
      2. Qdrant top-k search (k=5) by cosine
      3. (Optional) rerank → keep top 3–4 for precision
      4. Build prompt: system (answer only from context, cite sources)
         + retrieved chunks
         + last ~6 chat_messages of the session
      5. Stream LLM tokens → SSE to frontend
      6. Emit final sources event (file + page + snippet)
      7. Persist user message + assistant message to chat_messages
  → Frontend renders tokens live, then appends source chips
```

Memory: the last ~6 messages of the session are folded into the prompt for follow-up context. Retrieval is always run against the current question. Pronoun/coreference rewriting is **not** in v1.

### 5.3 Concurrency

- FastAPI async: many `/chat` requests in flight simultaneously (each awaiting Ollama) without blocking each other.
- Ollama queues generations internally; set `OLLAMA_NUM_PARALLEL` on the Ollama host so a couple generate at once while others wait briefly. Streaming keeps perceived latency low.
- Embedding calls (ingestion + query) are small/fast and won't starve the LLM.

## 6. Error Handling & Edge Cases

- **No relevant context** → if top Qdrant score is below threshold, bot responds "I couldn't find this in the manuals" rather than hallucinating. System prompt hard rule: *answer only from retrieved context*.
- **Ingestion failure** → `documents.status=failed` + `error` message; frontend shows it so the file can be re-uploaded. A bad file never breaks the pipeline.
- **OCR fallback** → automatic for text-less PDF pages; `parser_used=ocr` flags lower-quality files.
- **Ollama unreachable / slow** → `/chat` returns 503 with a clear message; ingestion retries embeddings with backoff. Frontend shows "AI service unavailable" instead of hanging.
- **Large files** → embedding in batches with progress persisted; a 500-page manual won't time out.
- **Unsupported file type** → rejected at upload with a clear message before ingestion starts.

## 7. Testing Strategy

- **Retrieval quality (highest priority):** a small set of manual-derived Q&A pairs as a smoke test — verify the right chunk is retrieved for known questions. Run after each retrieval-tuning change.
- **Backend unit tests (pytest):** parser routing, chunking, prompt assembly, no-context threshold, Postgres repository functions. Ollama mocked.
- **API integration tests:** `/documents` upload→status flow, `/chat` SSE stream shape, source emission — against real Qdrant + Postgres via a test docker-compose.
- **Frontend:** Vitest for utilities + a Playwright smoke test (load page, ask a question, see streamed answer + source chip).
- **Manual end-to-end:** on the real box with one real manual before client handoff.

## 8. Out of Scope (v1)

- Authentication / user management / login (planned for a later phase)
- Pronoun/coreference query rewriting
- Reranking may be optional in the first cut (behind a flag)
- Usage analytics / admin dashboards

## 9. Open Items / Assumptions

- Exact manual formats and volume are unknown; ingestion is built defensively to handle the mix.
- Default LLM is `qwen2.5:32b`; final choice confirmed once the client's Ollama host is available.
- Default chunk size 512 tokens / 50 overlap; tunable after retrieval-quality testing.