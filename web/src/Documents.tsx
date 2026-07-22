import { useEffect, useRef, useState } from "react";
import { uploadDocument, listDocuments, deleteDocument } from "./api";
import { DocumentRow } from "./types";

const INFLIGHT = new Set(["pending", "parsing", "embedding"]);

export function Documents() {
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const docsRef = useRef<DocumentRow[]>([]);

  async function refresh() {
    try { setDocs(await listDocuments()); } catch { /* ignore transient */ }
  }

  useEffect(() => { docsRef.current = docs; }, [docs]);

  useEffect(() => {
    refresh();
    const id = setInterval(() => {
      if (docsRef.current.some((d) => INFLIGHT.has(d.status))) refresh();
    }, 2000);
    return () => clearInterval(id);
  }, []); // mount once

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
