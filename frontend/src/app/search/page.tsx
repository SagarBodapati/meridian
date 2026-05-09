"use client";

import { useState } from "react";
import { Search, Loader2, ExternalLink } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { searchChunks } from "@/lib/api";
import type { SearchResult } from "@/lib/types";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [ticker, setTicker] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await searchChunks(query, ticker || undefined);
      setResults(data.results || []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
      setSearched(true);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-8">
          <h1 className="text-2xl font-bold text-slate-800 mb-1">Document Search</h1>
          <p className="text-slate-500 text-sm mb-6">
            Search directly across indexed SEC filings and transcripts
          </p>

          <div className="flex gap-2 mb-6">
            <input
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase().slice(0, 5))}
              placeholder="Ticker"
              className="w-24 font-mono text-sm px-3 py-2.5 border border-slate-200 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder='e.g. "services revenue growth guidance"'
              className="flex-1 text-sm px-3 py-2.5 border border-slate-200 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <button
              onClick={handleSearch}
              disabled={loading || !query.trim()}
              className="px-4 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-xl hover:bg-brand-700 disabled:opacity-40 flex items-center gap-2"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
              Search
            </button>
          </div>

          {searched && results.length === 0 && !loading && (
            <p className="text-slate-500 text-sm text-center py-8">
              No results found. Try different keywords or ensure the company is indexed.
            </p>
          )}

          <div className="flex flex-col gap-3">
            {results.map((r, i) => (
              <div key={r.chunk_id} className="bg-white border border-slate-200 rounded-xl p-4">
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-slate-400">#{i + 1}</span>
                    <span className="text-xs font-semibold text-brand-700 bg-brand-50 px-2 py-0.5 rounded-full">
                      {r.ticker}
                    </span>
                    <span className="text-xs text-slate-500">{r.filing_type} · {r.fiscal_period}</span>
                    <span className="text-xs text-slate-400">{r.section}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">
                      score: {r.rerank_score.toFixed(3)}
                    </span>
                    {r.source_url && (
                      <a href={r.source_url} target="_blank" rel="noopener noreferrer"
                        className="text-slate-400 hover:text-brand-600">
                        <ExternalLink size={12} />
                      </a>
                    )}
                  </div>
                </div>
                <p className="text-sm text-slate-700 leading-relaxed line-clamp-5">{r.text}</p>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
