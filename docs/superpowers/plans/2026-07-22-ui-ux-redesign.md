# RAG Studio UI/UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the barebones RAG Studio web prototype into an executive-grade SaaS application with dual light/dark themes, responsive 3-zone layout, streaming chat with interactive citation drawers, and document management.

**Architecture:** Vanilla CSS design token system (`web/src/styles.css`) driven by a React Theme Context (`data-theme="light"` / `"dark"`). Lucide SVG icon components, React state for active tabs and collapsible right drawer, and CSS grid/flexbox responsive layout.

**Tech Stack:** React, TypeScript, Vite, Vanilla CSS.

## Global Constraints

- CSS variables used exclusively for styling and theming (`--bg-app`, `--bg-surface`, `--accent-primary`, etc.).
- No external heavy CSS frameworks or emoji icons as structural UI icons.
- All interactive controls have minimum 44×44px touch targets and `:focus-visible` 2px ring focus states.
- 4.5:1 minimum text contrast ratio across both Light and Dark themes.

---

### Task 1: CSS Design Tokens & Base Global Styles

**Files:**
- Modify: `web/src/styles.css`

**Interfaces:**
- Produces: CSS color/typography variables (`--bg-app`, `--bg-surface`, `--text-primary`, `--accent-primary`, etc.) for Light & Dark themes.

- [ ] **Step 1: Write CSS Variables and Base Layout Rules**

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-normal: 250ms cubic-bezier(0.4, 0, 0.2, 1);
}

html[data-theme="light"] {
  --bg-app: #F8FAFC;
  --bg-surface: #FFFFFF;
  --bg-surface-hover: #F1F5F9;
  --bg-sidebar: #0F172A;
  --text-sidebar: #F8FAFC;
  --text-sidebar-muted: #94A3B8;
  --border-color: #E2E8F0;
  --border-focus: #2563EB;
  --text-primary: #0F172A;
  --text-secondary: #475569;
  --text-muted: #94A3B8;
  --accent-primary: #2563EB;
  --accent-hover: #1D4ED8;
  --accent-subtle: #EFF6FF;
  --status-success: #16A34A;
  --status-warning: #CA8A04;
  --status-error: #DC2626;
  --code-bg: #1E293B;
  --code-text: #E2E8F0;
}

html[data-theme="dark"] {
  --bg-app: #090D16;
  --bg-surface: #111827;
  --bg-surface-hover: #1F2937;
  --bg-sidebar: #0B0F19;
  --text-sidebar: #F9FAFB;
  --text-sidebar-muted: #6B7280;
  --border-color: #1F2937;
  --border-focus: #3B82F6;
  --text-primary: #F9FAFB;
  --text-secondary: #9CA3AF;
  --text-muted: #6B7280;
  --accent-primary: #3B82F6;
  --accent-hover: #60A5FA;
  --accent-subtle: #1E2640;
  --status-success: #22C55E;
  --status-warning: #EAB308;
  --status-error: #EF4444;
  --code-bg: #030712;
  --code-text: #F3F4F6;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--font-sans);
  background-color: var(--bg-app);
  color: var(--text-primary);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

:focus-visible {
  outline: 2px solid var(--border-focus);
  outline-offset: 2px;
}
```

- [ ] **Step 2: Verify CSS formatting in test runner**

Run: `npm --prefix web test`
Expected: Tests pass cleanly.

- [ ] **Step 3: Commit**

```bash
git add web/src/styles.css
git commit -m "style: add dual light/dark CSS design tokens"
```

---

### Task 2: Vector Icon Primitives & Theme State Context

**Files:**
- Create: `web/src/components/Icons.tsx`
- Create: `web/src/components/ThemeContext.tsx`

**Interfaces:**
- Produces: `useTheme()` hook returning `{ theme: 'light' | 'dark', toggleTheme: () => void }`.
- Produces: Clean SVG Icon components (`MessageIcon`, `FileTextIcon`, `SunIcon`, `MoonIcon`, `PlusIcon`, `XIcon`, `CopyIcon`, `CheckIcon`, `TrashIcon`).

- [ ] **Step 1: Create Icons.tsx**

```tsx
import React from 'react';

export function MessageIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

export function FileTextIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

export function SunIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}

export function MoonIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

export function PlusIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

export function XIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}
```

- [ ] **Step 2: Create ThemeContext.tsx**

```tsx
import React, { createContext, useContext, useEffect, useState } from 'react';

type Theme = 'light' | 'dark';

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    return (localStorage.getItem('rag_theme') as Theme) || 'dark';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('rag_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme must be used within ThemeProvider');
  return context;
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/Icons.tsx web/src/components/ThemeContext.tsx
git commit -m "feat: add SVG vector icon primitives and light/dark ThemeProvider"
```

---

### Task 3: Executive Header & Sidebar Workspace Shell

**Files:**
- Create: `web/src/components/Header.tsx`
- Create: `web/src/components/Sidebar.tsx`
- Modify: `web/src/App.tsx`

**Interfaces:**
- Consumes: `useTheme()`, `MessageIcon`, `FileTextIcon`, `SunIcon`, `MoonIcon`, `PlusIcon`.
- Produces: Responsive 3-zone app layout wrapper.

- [ ] **Step 1: Create Header.tsx**

```tsx
import React from 'react';
import { useTheme } from './ThemeContext';
import { SunIcon, MoonIcon } from './Icons';

export function Header({ activeTab }: { activeTab: 'chat' | 'documents' }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="app-header">
      <div className="header-left">
        <h1 className="logo-text">RAG Studio <span className="version-badge">v1.0</span></h1>
        <div className="tab-indicator">
          Workspace / <span>{activeTab === 'chat' ? 'Chat Assistant' : 'Document Library'}</span>
        </div>
      </div>
      <div className="header-right">
        <div className="status-pill">
          <span className="dot dot-success"></span> Qdrant DB
        </div>
        <div className="status-pill">
          <span className="dot dot-success"></span> Ollama LLM
        </div>
        <button
          className="theme-toggle-btn"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
        >
          {theme === 'light' ? <MoonIcon size={18} /> : <SunIcon size={18} />}
        </button>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Create Sidebar.tsx**

```tsx
import React from 'react';
import { MessageIcon, FileTextIcon, PlusIcon } from './Icons';

interface SidebarProps {
  activeTab: 'chat' | 'documents';
  setTab: (tab: 'chat' | 'documents') => void;
  onNewChat?: () => void;
}

export function Sidebar({ activeTab, setTab, onNewChat }: SidebarProps) {
  return (
    <aside className="app-sidebar">
      <button className="new-chat-btn" onClick={onNewChat}>
        <PlusIcon size={18} />
        <span>New Conversation</span>
      </button>

      <nav className="nav-menu">
        <button
          className={`nav-item ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setTab('chat')}
        >
          <MessageIcon size={18} />
          <span>Chat Workspace</span>
        </button>

        <button
          className={`nav-item ${activeTab === 'documents' ? 'active' : ''}`}
          onClick={() => setTab('documents')}
        >
          <FileTextIcon size={18} />
          <span>Documents Library</span>
        </button>
      </nav>
    </aside>
  );
}
```

- [ ] **Step 3: Update App.tsx to assemble layout shell**

```tsx
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
```

- [ ] **Step 4: Commit**

```bash
git add web/src/components/Header.tsx web/src/components/Sidebar.tsx web/src/App.tsx
git commit -m "feat: implement header and sidebar responsive workspace layout shell"
```

---

### Task 4: Right Citation Drawer Component

**Files:**
- Create: `web/src/components/CitationDrawer.tsx`

**Interfaces:**
- Consumes: Selected chunk citation details (`{ filename: string, chunkId: string, text: string, score: number }`).
- Produces: Collapsible side panel with match percentage and metadata.

- [ ] **Step 1: Create CitationDrawer.tsx**

```tsx
import React from 'react';
import { XIcon } from './Icons';

export interface CitationData {
  filename: string;
  chunkId: string;
  text: string;
  score: number;
}

interface CitationDrawerProps {
  citation: CitationData | null;
  onClose: () => void;
}

export function CitationDrawer({ citation, onClose }: CitationDrawerProps) {
  if (!citation) return null;

  return (
    <aside className="citation-drawer">
      <div className="drawer-header">
        <h3>Source Citation</h3>
        <button className="icon-btn" onClick={onClose} aria-label="Close drawer">
          <XIcon size={18} />
        </button>
      </div>
      <div className="drawer-body">
        <div className="citation-meta">
          <span className="file-name">{citation.filename}</span>
          <span className="score-badge">{(citation.score * 100).toFixed(1)}% Match</span>
        </div>
        <div className="chunk-id-tag">Chunk ID: {citation.chunkId}</div>
        <div className="chunk-content-box">
          <pre>{citation.text}</pre>
        </div>
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/components/CitationDrawer.tsx
git commit -m "feat: add right citation drawer for chunk inspection"
```

---

### Task 5: Streaming Chat Component & Inline Citations Redesign

**Files:**
- Modify: `web/src/Chat.tsx`

**Interfaces:**
- Consumes: `CitationDrawer` component and citation click handler.
- Produces: Enhanced chat interface with inline citation pills `[1]`, `[2]` and prompt suggestion chips.

- [ ] **Step 1: Enhance Chat.tsx with citations and sleek styling**

Update `web/src/Chat.tsx` to handle inline citation pills, open `CitationDrawer`, and present prompt suggestions when messages array is empty.

- [ ] **Step 2: Run web unit tests to verify behavior**

Run: `npm --prefix web test`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add web/src/Chat.tsx
git commit -m "feat: add prompt pills and inline interactive citation drawer to Chat"
```

---

### Task 6: Document Management Library Redesign

**Files:**
- Modify: `web/src/Documents.tsx`

**Interfaces:**
- Produces: Polished drag-and-drop file upload zone, ingestion status badges (`Indexed`, `Processing`, `Error`), and document data table.

- [ ] **Step 1: Update Documents.tsx with drag-and-drop zone and clean status indicators**

Update `web/src/Documents.tsx` with dropzone styling, status pills, and empty states.

- [ ] **Step 2: Run web unit tests**

Run: `npm --prefix web test`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add web/src/Documents.tsx
git commit -m "feat: add dropzone and indexed document table to Documents view"
```

---

### Task 7: CSS Stylesheet Integration & Verification Test

**Files:**
- Modify: `web/src/styles.css`

- [ ] **Step 1: Add layout grid, sidebar, drawer, header, and chat CSS rules**

Complete `web/src/styles.css` with layout flexbox/grid classes (`.app-layout`, `.app-header`, `.app-sidebar`, `.citation-drawer`, `.prompt-pill`, `.citation-pill`, `.status-pill`, etc.).

- [ ] **Step 2: Run frontend build check**

Run: `npm --prefix web run build`
Expected: Build passes with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add web/src/styles.css
git commit -m "style: finalize CSS stylesheet for RAG Studio SaaS interface"
```
