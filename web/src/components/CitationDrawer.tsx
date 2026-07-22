import { useEffect, useRef } from 'react';
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
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!citation) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [citation, onClose]);

  if (!citation) return null;

  return (
    <>
      <button className="drawer-backdrop" aria-hidden="true" tabIndex={-1} onClick={onClose} />
      <aside className="citation-drawer" role="dialog" aria-modal="true" aria-label="Source citation">
        <div className="drawer-header">
          <h3>Source Citation</h3>
          <button className="icon-btn" ref={closeRef} onClick={onClose} aria-label="Close drawer">
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
    </>
  );
}
