import { createParser } from "eventsource-parser";
import type { Citation, StreamEvent } from "./types";

const BACKEND = "/api/backend";

export async function* streamChat(
  message: string,
  sessionId: string,
  history: Array<{ role: string; content: string }>,
  filters: Record<string, string> = {}
): AsyncGenerator<StreamEvent> {
  const resp = await fetch(`${BACKEND}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, history, filters }),
  });

  if (!resp.ok) {
    throw new Error(`API error: ${resp.status}`);
  }

  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();

  const parser = createParser({
    onEvent(event) {
      // Handled below via queue
    },
  });

  // Manual SSE parsing for async generator compatibility
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const event: StreamEvent = JSON.parse(line.slice(6));
          yield event;
        } catch {
          // skip malformed
        }
      }
    }
  }
}

export async function ingestTicker(
  ticker: string,
  filingTypes = ["10-K", "10-Q"],
  yearsBack = 3
) {
  const resp = await fetch(`${BACKEND}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ticker,
      filing_types: filingTypes,
      years_back: yearsBack,
    }),
  });
  return resp.json();
}

export async function getIngestionStatus(ticker: string) {
  const resp = await fetch(`${BACKEND}/ingest/status/${ticker}`);
  return resp.json();
}

export async function getCompanyProfile(ticker: string) {
  const resp = await fetch(`${BACKEND}/reports/company/${ticker}`);
  return resp.json();
}

export async function searchChunks(
  query: string,
  ticker?: string,
  filingType?: string
) {
  const resp = await fetch(`${BACKEND}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, ticker, filing_type: filingType, top_k: 10 }),
  });
  return resp.json();
}
