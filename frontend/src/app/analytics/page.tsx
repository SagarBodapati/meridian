"use client";

import { useState } from "react";
import { BarChart2, Loader2, TrendingUp } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { getCompanyProfile } from "@/lib/api";
import type { CompanyProfile } from "@/lib/types";

export default function AnalyticsPage() {
  const [ticker, setTicker] = useState("");
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadProfile = async () => {
    if (!ticker.trim()) return;
    setLoading(true);
    setError("");
    try {
      const data = await getCompanyProfile(ticker.trim());
      setProfile(data);
    } catch {
      setError("Failed to load company profile. Ensure the company is indexed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-6 py-8">
          <h1 className="text-2xl font-bold text-slate-800 mb-1">Company Analytics</h1>
          <p className="text-slate-500 text-sm mb-6">Knowledge graph insights and recent news</p>

          <div className="flex gap-2 mb-8">
            <input
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase().slice(0, 5))}
              onKeyDown={(e) => e.key === "Enter" && loadProfile()}
              placeholder="Enter ticker (e.g. AAPL)"
              className="font-mono text-sm px-3 py-2.5 border border-slate-200 rounded-xl bg-white w-48 focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <button
              onClick={loadProfile}
              disabled={loading || !ticker.trim()}
              className="px-4 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-xl hover:bg-brand-700 disabled:opacity-40 flex items-center gap-2"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <BarChart2 size={14} />}
              Load Profile
            </button>
          </div>

          {error && (
            <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg px-4 py-2 mb-4">
              {error}
            </p>
          )}

          {profile && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Executives */}
              <div className="bg-white border border-slate-200 rounded-xl p-4">
                <h3 className="font-semibold text-slate-800 text-sm mb-3 flex items-center gap-2">
                  <TrendingUp size={14} className="text-brand-600" /> Leadership
                </h3>
                {profile.executives.length > 0 ? (
                  <ul className="divide-y divide-slate-100">
                    {profile.executives.map((e) => (
                      <li key={e.name} className="py-1.5 flex items-center justify-between">
                        <span className="text-sm font-medium text-slate-700">{e.name}</span>
                        <span className="text-xs text-slate-400">{e.role}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-slate-400">No leadership data indexed</p>
                )}
              </div>

              {/* Peer Set */}
              <div className="bg-white border border-slate-200 rounded-xl p-4">
                <h3 className="font-semibold text-slate-800 text-sm mb-3">Peer Set</h3>
                {profile.peer_set.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {profile.peer_set.map((t) => (
                      <span key={t} className="text-xs font-mono font-semibold bg-brand-50 text-brand-700 px-2.5 py-1 rounded-full border border-brand-100">
                        {t}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-400">No peer data available</p>
                )}
              </div>

              {/* Recent News */}
              <div className="bg-white border border-slate-200 rounded-xl p-4 md:col-span-2">
                <h3 className="font-semibold text-slate-800 text-sm mb-3">Recent News</h3>
                {profile.recent_news.length > 0 ? (
                  <ul className="divide-y divide-slate-100">
                    {profile.recent_news.map((n) => (
                      <li key={n.url} className="py-2.5">
                        <a
                          href={n.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-brand-700 hover:text-brand-900 font-medium hover:underline"
                        >
                          {n.title}
                        </a>
                        <div className="flex gap-2 mt-0.5">
                          <span className="text-xs text-slate-400">{n.source}</span>
                          <span className="text-xs text-slate-300">·</span>
                          <span className="text-xs text-slate-400">
                            {new Date(n.published).toLocaleDateString()}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-slate-400">No recent news found</p>
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
