"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Trash2, TrendingUp, BarChart2, FileSearch, BookOpen } from "lucide-react";
import { useChat } from "@/hooks/useChat";
import { Message } from "./Message";

const EXAMPLE_QUERIES = [
  { icon: TrendingUp, text: "How has Apple's services revenue trended over the last 8 quarters?" },
  { icon: BarChart2,  text: "Compare NVIDIA vs AMD gross margins in 2024" },
  { icon: FileSearch, text: "What are the key risk factors disclosed in Tesla's most recent 10-K?" },
  { icon: BookOpen,   text: "Generate a research report on Microsoft's cloud business" },
];

export function ChatWindow() {
  const { messages, isLoading, sendMessage, clearMessages } = useChat();
  const [input, setInput] = useState("");
  const [ticker, setTicker] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = (text?: string) => {
    const query = text ?? input.trim();
    if (!query) return;
    const filters: Record<string, string> = {};
    if (ticker) filters.ticker = ticker.toUpperCase();
    sendMessage(query, filters);
    setInput("");
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <EmptyState onSelect={(q) => handleSubmit(q)} />
        ) : (
          <div className="py-4">
            {messages.map((msg) => (
              <Message key={msg.id} message={msg} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="border-t border-slate-200 bg-white px-4 py-3">
        <div className="max-w-3xl mx-auto flex flex-col gap-2">
          {/* Ticker filter */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Filter by ticker:</span>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase().slice(0, 5))}
              placeholder="AAPL"
              className="w-20 text-xs px-2 py-1 border border-slate-200 rounded-md bg-slate-50 font-mono focus:outline-none focus:ring-1 focus:ring-brand-500 uppercase"
            />
            {messages.length > 0 && (
              <button
                onClick={clearMessages}
                className="ml-auto text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1"
              >
                <Trash2 size={12} /> Clear
              </button>
            )}
          </div>

          {/* Text input */}
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask about financial filings, earnings, trends, or request a report..."
              rows={2}
              className="flex-1 resize-none text-sm px-3 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent placeholder-slate-400"
            />
            <button
              onClick={() => handleSubmit()}
              disabled={isLoading || !input.trim()}
              className="self-end px-4 py-2.5 bg-brand-600 text-white rounded-xl hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5 text-sm font-medium"
            >
              <Send size={14} />
            </button>
          </div>
          <p className="text-[11px] text-slate-400 text-center">
            Grounded in SEC filings, earnings calls, and financial news. Always verify critical decisions with primary sources.
          </p>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ onSelect }: { onSelect: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[60vh] px-4">
      <div className="w-12 h-12 bg-brand-600 rounded-2xl flex items-center justify-center mb-4 shadow-lg shadow-brand-200">
        <TrendingUp className="text-white" size={24} />
      </div>
      <h2 className="text-2xl font-semibold text-slate-800 mb-1">Meridian</h2>
      <p className="text-slate-500 text-sm mb-8 text-center max-w-md">
        Your financial research copilot. Grounded in SEC filings, earnings transcripts, and financial news.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl">
        {EXAMPLE_QUERIES.map(({ icon: Icon, text }) => (
          <button
            key={text}
            onClick={() => onSelect(text)}
            className="flex items-start gap-3 text-left px-4 py-3 bg-white border border-slate-200 rounded-xl hover:border-brand-300 hover:bg-brand-50 transition-colors group"
          >
            <Icon size={16} className="text-brand-500 mt-0.5 flex-shrink-0 group-hover:text-brand-700" />
            <span className="text-sm text-slate-600 group-hover:text-slate-800">{text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
