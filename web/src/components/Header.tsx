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
