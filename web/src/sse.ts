import { Source } from "./types";

export type ChatEvent =
  | { type: "session"; session_id: number }
  | { type: "token"; content: string }
  | { type: "sources"; sources: Source[] }
  | { type: "done" };

export function parseSseEvents(text: string): ChatEvent[] {
  const events: ChatEvent[] = [];
  for (const block of text.split("\n\n")) {
    for (const line of block.split("\n")) {
      if (line.startsWith("data: ")) {
        try {
          events.push(JSON.parse(line.slice(6)) as ChatEvent);
        } catch {
          // skip malformed line
        }
      }
    }
  }
  return events;
}

export async function streamChat(
  question: string,
  sessionId: number | null,
  onEvent: (e: ChatEvent) => void,
  onError: (err: Error) => void,
): Promise<void> {
  let resp: Response;
  try {
    resp = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, session_id: sessionId }),
    });
  } catch (e) {
    onError(e as Error);
    return;
  }
  if (!resp.ok || !resp.body) {
    onError(new Error(`${resp.status} ${resp.statusText}`.trim()));
    return;
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      for (const line of block.split("\n")) {
        if (line.startsWith("data: ")) {
          try {
            onEvent(JSON.parse(line.slice(6)) as ChatEvent);
          } catch {
            // skip malformed line
          }
        }
      }
    }
  }
}
