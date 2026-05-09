"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { User, Bot, Loader2 } from "lucide-react";
import type { ChatMessage } from "@/lib/types";
import { CitationList } from "./Citations";
import { QueryTypeBadge } from "./QueryTypeBadge";
import { cn } from "@/lib/utils";

interface MessageProps {
  message: ChatMessage;
}

export function Message({ message }: MessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3 px-4 py-4", isUser ? "flex-row-reverse" : "flex-row")}>
      {/* Avatar */}
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
          isUser ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600"
        )}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>

      {/* Bubble */}
      <div className={cn("flex flex-col gap-2 max-w-3xl", isUser ? "items-end" : "items-start")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm leading-relaxed",
            isUser
              ? "bg-brand-600 text-white rounded-tr-sm"
              : "bg-white border border-slate-200 text-slate-800 rounded-tl-sm shadow-sm"
          )}
        >
          {isUser ? (
            <p>{message.content}</p>
          ) : (
            <>
              {message.isStreaming && !message.content ? (
                <div className="flex items-center gap-2 text-slate-400">
                  <Loader2 size={14} className="animate-spin" />
                  <span className="text-xs">Thinking...</span>
                </div>
              ) : (
                <div className="prose prose-sm prose-slate max-w-none">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      table: ({ children }) => (
                        <div className="overflow-x-auto my-3">
                          <table className="min-w-full text-xs border-collapse">{children}</table>
                        </div>
                      ),
                      th: ({ children }) => (
                        <th className="border border-slate-200 bg-slate-50 px-3 py-1.5 text-left font-semibold text-slate-700">
                          {children}
                        </th>
                      ),
                      td: ({ children }) => (
                        <td className="border border-slate-200 px-3 py-1.5 text-slate-700">
                          {children}
                        </td>
                      ),
                      code: ({ children, className }) => {
                        const isBlock = className?.includes("language-");
                        return isBlock ? (
                          <pre className="bg-slate-50 border border-slate-200 rounded-lg p-3 overflow-x-auto text-xs">
                            <code>{children}</code>
                          </pre>
                        ) : (
                          <code className="bg-slate-100 px-1 py-0.5 rounded text-xs font-mono">
                            {children}
                          </code>
                        );
                      },
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                  {message.isStreaming && (
                    <span className="inline-block w-1 h-4 bg-brand-500 animate-pulse ml-0.5 align-text-bottom" />
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Metadata row */}
        {!isUser && !message.isStreaming && (
          <div className="flex items-center gap-2 px-1">
            {message.queryType && <QueryTypeBadge type={message.queryType} />}
            <span className="text-xs text-slate-400">
              {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
        )}

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <CitationList citations={message.citations} />
        )}
      </div>
    </div>
  );
}
