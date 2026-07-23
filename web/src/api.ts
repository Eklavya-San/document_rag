import { DocumentRow, StoredMessage, HealthResponse } from "./types";

async function jsonOrThrow<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      if (body && body.detail) detail = body.detail;
    } catch {
      // non-JSON body; fall back to status text
    }
    throw new Error(`${resp.status} ${detail}`.trim());
  }
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

export async function fetchHealth(): Promise<HealthResponse> {
  const resp = await fetch("/health");
  return jsonOrThrow<HealthResponse>(resp);
}

export async function fetchSessionMessages(sessionId: number): Promise<StoredMessage[]> {
  const resp = await fetch(`/chat/sessions/${sessionId}/messages`);
  return jsonOrThrow<StoredMessage[]>(resp);
}

export async function sendFeedback(messageId: number, rating: 1 | -1): Promise<void> {
  const resp = await fetch(`/chat/messages/${messageId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating }),
  });
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`.trim());
}

