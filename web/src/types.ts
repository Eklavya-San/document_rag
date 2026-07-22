export interface DocumentRow {
  id: number;
  filename: string;
  status: "pending" | "parsing" | "embedding" | "done" | "failed";
  chunk_count: number;
  parser_used: string | null;
  error: string | null;
}

export interface Source {
  filename: string;
  page: number;
  text: string;
  score: number;
}

export interface StoredMessage {
  role: "user" | "assistant";
  content: string;
  sources: Source[];
}
