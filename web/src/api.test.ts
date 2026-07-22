import { describe, it, expect, vi, beforeEach } from "vitest";
import { uploadDocument, listDocuments, deleteDocument, fetchSessionMessages } from "./api";

describe("api helpers", () => {
  beforeEach(() => { (globalThis as any).fetch = vi.fn(); });

  it("uploadDocument POSTs multipart and returns the row", async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: true, json: async () => ({ id: 1, filename: "m.pdf", status: "pending", chunk_count: 0, parser_used: null, error: null }) });
    const row = await uploadDocument(new File(["x"], "m.pdf"));
    expect(row.id).toBe(1);
    const [url, opts] = (globalThis.fetch as any).mock.calls[0];
    expect(url).toBe("/documents/upload");
    expect(opts.method).toBe("POST");
    expect(opts.body).toBeInstanceOf(FormData);
  });

  it("listDocuments GETs /documents", async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: true, json: async () => [{ id: 1, filename: "m.pdf", status: "done", chunk_count: 3, parser_used: "pdf", error: null }] });
    const docs = await listDocuments();
    expect(docs).toHaveLength(1);
    expect((globalThis.fetch as any).mock.calls[0][0]).toBe("/documents");
  });

  it("deleteDocument DELETEs /documents/:id", async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: true, status: 204 });
    await deleteDocument(7);
    const [url, opts] = (globalThis.fetch as any).mock.calls[0];
    expect(url).toBe("/documents/7");
    expect(opts.method).toBe("DELETE");
  });

  it("fetchSessionMessages GETs the session messages", async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: true, json: async () => [{ role: "user", content: "hi", sources: [] }] });
    const msgs = await fetchSessionMessages(5);
    expect(msgs[0].role).toBe("user");
    expect((globalThis.fetch as any).mock.calls[0][0]).toBe("/chat/sessions/5/messages");
  });

  it("throws on a non-ok response", async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: false, status: 503, statusText: "AI service unavailable" });
    await expect(listDocuments()).rejects.toThrow("503");
  });
});
