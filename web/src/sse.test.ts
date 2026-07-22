import { describe, it, expect, vi } from "vitest";
import { parseSseEvents, streamChat } from "./sse";

describe("parseSseEvents", () => {
  it("parses session/token/sources/done events", () => {
    const text = [
      'data: {"type":"session","session_id":42}',
      "",
      'data: {"type":"token","content":"Hel"}',
      "",
      'data: {"type":"token","content":"lo"}',
      "",
      'data: {"type":"sources","sources":[{"filename":"m.pdf","page":3,"text":"calibrate","score":0.9}]}',
      "",
      'data: {"type":"done"}',
      "",
    ].join("\n");
    const events = parseSseEvents(text);
    expect(events).toHaveLength(5);
    expect(events[0]).toEqual({ type: "session", session_id: 42 });
    expect(events[1]).toEqual({ type: "token", content: "Hel" });
    expect(events[3].type).toBe("sources");
    expect(events[4].type).toBe("done");
  });

  it("ignores non-data lines", () => {
    const text = "event: ping\ndata: {\"type\":\"done\"}\n\n";
    const events = parseSseEvents(text);
    expect(events).toEqual([{ type: "done" }]);
  });
});

describe("streamChat", () => {
  it("calls onEvent for each event from the stream", async () => {
    const encoder = new TextEncoder();
    const chunks = [
      encoder.encode('data: {"type":"session","session_id":1}\n\n'),
      encoder.encode('data: {"type":"token","content":"Hi"}\n\n'),
      encoder.encode('data: {"type":"done"}\n\n'),
    ];
    let i = 0;
    const stream = new ReadableStream({
      pull(controller) { controller.enqueue(chunks[i++]); if (i >= chunks.length) controller.close(); },
    });
    (globalThis as any).fetch = vi.fn().mockResolvedValue({ ok: true, body: stream });

    const events: any[] = [];
    await streamChat("hello", null, (e) => events.push(e), () => {});
    expect(events.map((e) => e.type)).toEqual(["session", "token", "done"]);
    expect((globalThis.fetch as any).mock.calls[0][1].method).toBe("POST");
  });

  it("calls onError on a non-ok response", async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValue({ ok: false, status: 503, statusText: "AI service unavailable" });
    let err: Error | null = null;
    await streamChat("hello", null, () => {}, (e) => { err = e; });
    expect(err).not.toBeNull();
    expect(err!.message).toContain("503");
  });

  it("skips malformed data lines without throwing", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"type":"token","content":"Hi"}\n\n'));
        controller.enqueue(encoder.encode('data: not-json\n\n'));
        controller.enqueue(encoder.encode('data: {"type":"done"}\n\n'));
        controller.close();
      },
    });
    (globalThis as any).fetch = vi.fn().mockResolvedValue({ ok: true, body: stream });
    const events: any[] = [];
    await streamChat("q", null, (e) => events.push(e), () => {});
    expect(events.map((e) => e.type)).toEqual(["token", "done"]);
  });
});
