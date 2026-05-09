"use client";

import { useState } from "react";
import { Upload, CheckCircle, Loader2, AlertCircle } from "lucide-react";
import { ingestTicker } from "@/lib/api";

type Status = "idle" | "loading" | "success" | "error";

export function IngestPanel() {
  const [ticker, setTicker] = useState("");
  const [years, setYears] = useState(3);
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");

  const handleIngest = async () => {
    if (!ticker.trim()) return;
    setStatus("loading");
    setMessage("");
    try {
      const result = await ingestTicker(ticker.trim(), ["10-K", "10-Q"], years);
      setStatus("success");
      setMessage(result.message || `Ingestion queued for ${ticker.toUpperCase()}`);
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "Ingestion failed");
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <Upload size={16} className="text-brand-600" />
        <h3 className="font-semibold text-slate-800 text-sm">Index New Company</h3>
      </div>

      <div className="flex flex-col gap-3">
        <div>
          <label className="text-xs text-slate-500 mb-1 block">Ticker symbol</label>
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase().slice(0, 5))}
            placeholder="AAPL"
            className="w-full font-mono text-sm px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div>
          <label className="text-xs text-slate-500 mb-1 block">Years of history</label>
          <select
            value={years}
            onChange={(e) => setYears(Number(e.target.value))}
            className="w-full text-sm px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
          >
            <option value={1}>1 year</option>
            <option value={2}>2 years</option>
            <option value={3}>3 years</option>
            <option value={5}>5 years</option>
          </select>
        </div>

        <button
          onClick={handleIngest}
          disabled={status === "loading" || !ticker.trim()}
          className="flex items-center justify-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {status === "loading" ? (
            <><Loader2 size={14} className="animate-spin" /> Indexing...</>
          ) : (
            <><Upload size={14} /> Index Filings</>
          )}
        </button>

        {status === "success" && (
          <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
            <CheckCircle size={14} />
            {message}
          </div>
        )}
        {status === "error" && (
          <div className="flex items-center gap-2 text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            <AlertCircle size={14} />
            {message}
          </div>
        )}
      </div>
    </div>
  );
}
