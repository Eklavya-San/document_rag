import { useEffect, useRef, useState } from "react";
import { uploadDocument, listDocuments, deleteDocument } from "./api";
import { DocumentRow } from "./types";
import { UploadIcon, TrashIcon, FileTextIcon } from "./components/Icons";

const INFLIGHT = new Set(["pending", "parsing", "embedding", "processing"]);

export function Documents() {
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const docsRef = useRef<DocumentRow[]>([]);

  async function refresh() {
    try {
      setDocs(await listDocuments());
    } catch {
      /* ignore transient */
    }
  }

  useEffect(() => {
    docsRef.current = docs;
  }, [docs]);

  useEffect(() => {
    refresh();
    const id = setInterval(() => {
      if (docsRef.current.some((d) => INFLIGHT.has(d.status))) refresh();
    }, 2000);
    return () => clearInterval(id);
  }, []); // mount once

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setIsUploading(true);
    setUploadProgress(10);
    const fileArray = Array.from(files);
    for (let i = 0; i < fileArray.length; i++) {
      try {
        await uploadDocument(fileArray[i]);
      } catch {
        /* ignore */
      }
      setUploadProgress(Math.round(((i + 1) / fileArray.length) * 100));
    }
    await refresh();
    setTimeout(() => {
      setIsUploading(false);
      setUploadProgress(0);
    }, 400);
  }

  async function remove(id: number) {
    try {
      await deleteDocument(id);
    } catch {
      /* ignore */
    }
    refresh();
  }

  const getStatusPill = (doc: DocumentRow) => {
    if (doc.status === "done") {
      return <span className="status-pill status-indexed">Indexed</span>;
    }
    if (doc.status === "failed") {
      return (
        <span className="status-pill status-error" title={doc.error || "Ingestion error"}>
          Error
        </span>
      );
    }
    return <span className="status-pill status-processing">Processing</span>;
  };

  return (
    <div
      className="documents-container"
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      <div
        className={`dropzone ${dragOver ? "over" : ""}`}
        onClick={() => fileInput.current?.click()}
      >
        <div className="dropzone-icon">
          <UploadIcon size={36} />
        </div>
        <p className="dropzone-title">Drag & drop files here or click to browse</p>
        <p className="dropzone-hint">Supports PDF, TXT, MD, JSON</p>
        <input
          ref={fileInput}
          type="file"
          multiple
          accept=".pdf,.txt,.md,.json,.docx,.html,.htm"
          aria-label="Upload manual"
          onChange={(e) => handleFiles(e.target.files)}
          style={{ display: "none" }}
        />
      </div>

      {isUploading && (
        <div className="upload-progress-container">
          <div className="upload-progress-info">
            <span>Uploading documents...</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="upload-progress-bar">
            <div
              className="upload-progress-fill"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      <div className="doc-table-wrapper">
        <h2 className="section-title">Indexed Documents ({docs.length})</h2>
        {docs.length === 0 ? (
          <div className="empty-docs">No documents uploaded yet.</div>
        ) : (
          <table className="doc-table">
            <thead>
              <tr>
                <th>Document Title</th>
                <th>Chunk Count</th>
                <th>Status</th>
                <th className="actions-header">Actions</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id} className={`doc-row ${d.status}`}>
                  <td className="doc-title-cell">
                    <FileTextIcon size={18} />
                    <span className="doc-name">{d.filename}</span>
                  </td>
                  <td className="chunk-count-cell">{d.chunk_count ? `${d.chunk_count} chunks` : "-"}</td>
                  <td className="status-cell">
                    {getStatusPill(d)}
                    {d.error && <div className="doc-error">{d.error}</div>}
                  </td>
                  <td className="actions-cell">
                    <button
                      className="delete-btn"
                      onClick={() => remove(d.id)}
                      aria-label="Delete"
                    >
                      <TrashIcon size={16} />
                      <span>Delete</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
