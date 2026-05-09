export interface Citation {
  chunk_id: string;
  text: string;
  source: string;
  filing_type: string;
  company: string;
  fiscal_period: string;
  page_number?: number;
  url: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  queryType?: string;
  isStreaming?: boolean;
  timestamp: Date;
}

export interface StreamEvent {
  type: "token" | "citations" | "done" | "error";
  text?: string;
  citations?: Citation[];
  session_id?: string;
  query_type?: string;
  retrieved_chunks?: number;
  latency_ms?: number;
  model_used?: string;
  message?: string;
}

export interface CompanyProfile {
  ticker: string;
  executives: Array<{ name: string; role: string }>;
  competitors: string[];
  peer_set: string[];
  recent_news: Array<{
    title: string;
    url: string;
    published: string;
    source: string;
  }>;
}

export interface SearchResult {
  chunk_id: string;
  text: string;
  score: number;
  rerank_score: number;
  ticker: string;
  filing_type: string;
  fiscal_period: string;
  section: string;
  source_url: string;
}
