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
