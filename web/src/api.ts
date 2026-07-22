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
