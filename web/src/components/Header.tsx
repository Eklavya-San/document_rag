import { useEffect, useState } from 'react';
import { useTheme } from './ThemeContext';
import { SunIcon, MoonIcon } from './Icons';
import { fetchHealth } from '../api';

export function Header({ activeTab }: { activeTab: 'chat' | 'documents' }) {
  const { theme, toggleTheme } = useTheme();
  const [ollama, setOllama] = useState<string>('ok');
  const [qdrant, setQdrant] = useState<string>('ok');

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const h = await fetchHealth();
        if (!alive) return;
        setOllama(h.dependencies.ollama);
        setQdrant(h.dependencies.qdrant);
      } catch {
        if (alive) { setOllama('unreachable'); setQdrant('unreachable'); }
      }
    };
    poll();
    const id = setInterval(poll, 10000);
    return () => { alive = false; clearInterval(id); };
  }, []);

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
          <span className={`dot ${qdrant === 'ok' ? 'dot-success' : 'dot-error'}`}></span> Qdrant DB
        </div>
        <div className="status-pill">
          <span className={`dot ${ollama === 'ok' ? 'dot-success' : 'dot-error'}`}></span> Ollama LLM
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
