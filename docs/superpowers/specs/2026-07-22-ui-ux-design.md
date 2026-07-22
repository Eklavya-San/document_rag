# Design Specification: RAG Studio Executive SaaS UI/UX Redesign

**Date**: 2026-07-22  
**Status**: Approved  
**Aesthetic Style**: Clean Minimalist SaaS Executive Dual-Theme (Vanilla CSS Tokens + Lucide SVG Icons)  

---

## 1. Overview & Business Goals

The current RAG Studio frontend is a simple functional prototype. This design specification upgrades the user interface to an executive-grade SaaS application with dual light/dark themes, an intuitive 3-zone workspace layout, interactive citation inspection, and a polished document management suite.

---

## 2. Design System Tokens & Color Palette

### 2.1 CSS Variables (`web/src/styles.css`)

```css
/* Typography & Core Variables */
:root {
  --font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-normal: 250ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* Light Theme Variables */
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

/* Dark Theme Variables */
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
```

---

## 3. Layout Architecture

### 3.1 3-Zone Flexible Workspace

```
+---------------------------------------------------------------------------------------------+
|                                    TOP HEADER BAR                                           |
| Logo | App Title | Active Workspace Indicator | Qdrant & Ollama Status | Theme Toggle        |
+-------------------+----------------------------------------------------+--------------------+
| SIDEBAR           | MAIN WORKSPACE AREA                                | CITATION DRAWER    |
| (Collapsible)     |                                                    | (Collapsible)      |
| - New Chat        | [CHAT WORKSPACE / DOCUMENT LIBRARY]                | - Citation Details |
| - Workspace Nav   |                                                    | - Chunk Text       |
|   * Chat          | Message list with Markdown, Code blocks, and       | - Similarity Score |
|   * Documents     | inline clickable citation pills [1], [2].          | - Metadata Tag     |
|   * System Status |                                                    | - Document Link    |
| - Vector Stats    | Input box with Auto-expand text area & Send button|                    |
+-------------------+----------------------------------------------------+--------------------+
```

- **Top Header Bar**: Brand branding, connection status pills (Qdrant Vector DB & Ollama LLM health), Theme Toggle (Sun/Moon icon).
- **Sidebar (`Sidebar.tsx`)**: App navigation, "+ New Chat" button, document count badge, vector stats, collapsible on small viewports.
- **Main Workspace (`Chat.tsx` & `Documents.tsx`)**: Conversational stream canvas or document ingestion library.
- **Citation Inspection Drawer (`CitationDrawer.tsx`)**: Collapsible right side panel showing chunk details, vector similarity match percentage, and metadata.

---

## 4. Component Specifications

### 4.1 Navigation Sidebar (`Sidebar.tsx`)
- Brand header with "RAG Studio" heading and `v1.0` badge.
- "+ New Chat" quick action button.
- Workspace switcher items: Chat, Documents, System Health.
- Vector database summary card (total indexed vectors).
- Theme toggle switch with smooth SVG transition.

### 4.2 Streaming Chat & Citations (`Chat.tsx`)
- Hero section with quick start prompt pills.
- User bubble (right-aligned, subtle accent color background).
- Assistant bubble (left-aligned, markdown rendering, syntax highlighting, 1-click copy code snippet).
- Inline citation pills (`[1]`, `[2]`) that highlight on hover and open the Right Citation Drawer on click.
- Floating input container with auto-resizing text area, `Cmd/Ctrl + Enter` send trigger, and streaming progress state.

### 4.3 Right Citation Drawer (`CitationDrawer.tsx`)
- Slide-over drawer with header, close button (`X`), and document title.
- Similarity Match Badge (e.g. `94.5% Vector Match` in green).
- Raw chunk text preview in a monospaced text card.
- Chunk metadata (chunk index, file path, vector ID).

### 4.4 Document Library & Ingest Manager (`Documents.tsx`)
- Drag-and-drop file upload dropzone supporting `.pdf`, `.txt`, `.md`, `.json`.
- File ingestion progress indicator.
- Data table listing Document Name, File Size, Chunk Count, Status Badge (`Indexed`, `Processing`, `Error`), and Delete action.

---

## 5. Accessibility & UX Quality Controls

- **Text Contrast**: WCAG AAA compliant (>= 4.5:1 ratio for body text in both Light & Dark modes).
- **Touch Targets**: Minimum 44×44px interactive area for all buttons and nav triggers.
- **Keyboard Navigation**: Visible 2px focus ring (`:focus-visible`) across input elements and buttons.
- **Icon Discipline**: Crisp vector SVG icons with appropriate `aria-label` attributes (no emoji as structural icons).
- **Reduced Motion**: Respects `prefers-reduced-motion` for zero animation jarring.
