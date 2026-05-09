"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, ExternalLink, FileText } from "lucide-react";
import type { Citation } from "@/lib/types";

interface CitationListProps {
  citations: Citation[];
}

export function CitationList({ citations }: CitationListProps) {
  const [expanded, setExpanded] = useState(false);

  if (citations.length === 0) return null;

  const visible = expanded ? citations : citations.slice(0, 3);

  return (
    <div className="w-full max-w-3xl">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 transition-colors mb-2"
      >
        <FileText size={12} />
        <span>{citations.length} source{citations.length > 1 ? "s" : ""}</span>
        {citations.length > 3 && (
          expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />
        )}
      </button>

      <div className="flex flex-col gap-1.5">
        {visible.map((citation, i) => (
          <CitationCard key={citation.chunk_id} citation={citation} index={i + 1} />
        ))}
      </div>
    </div>
  );
}

interface CitationCardProps {
  citation: Citation;
  index: number;
}

function CitationCard({ citation, index }: CitationCardProps) {
  const [showText, setShowText] = useState(false);

  return (
    <div className="border border-slate-200 rounded-lg bg-slate-50 text-xs overflow-hidden">
      <div className="flex items-center justify-between gap-2 px-3 py-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="flex-shrink-0 w-5 h-5 rounded-full bg-brand-100 text-brand-700 font-semibold flex items-center justify-center text-[10px]">
            {index}
          </span>
          <div className="min-w-0">
            <p className="font-medium text-slate-700 truncate">{citation.source}</p>
            <p className="text-slate-400">{citation.filing_type} · {citation.fiscal_period}</p>
          </div>
        </div>

        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={() => setShowText((v) => !v)}
            className="text-slate-400 hover:text-slate-600 transition-colors p-1 rounded"
            title="Show excerpt"
          >
            {showText ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          {citation.url && (
            <a
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 hover:text-brand-600 transition-colors p-1 rounded"
              title="Open source"
            >
              <ExternalLink size={12} />
            </a>
          )}
        </div>
      </div>

      {showText && citation.text && (
        <div className="px-3 pb-2 border-t border-slate-200 pt-2">
          <p className="text-slate-600 leading-relaxed line-clamp-4">{citation.text}</p>
        </div>
      )}
    </div>
  );
}
