"use client";

import { useCallback, useRef, useState } from "react";
import { v4 as uuid } from "uuid";
import { streamChat } from "@/lib/api";
import type { ChatMessage, Citation } from "@/lib/types";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(() => uuid());
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (content: string, filters: Record<string, string> = {}) => {
      if (!content.trim() || isLoading) return;

      const userMsg: ChatMessage = {
        id: uuid(),
        role: "user",
        content,
        timestamp: new Date(),
      };

      const assistantId = uuid();
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        isStreaming: true,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsLoading(true);

      const history = messages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      try {
        let citations: Citation[] = [];

        for await (const event of streamChat(content, sessionId, history, filters)) {
          if (event.type === "token" && event.text) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: m.content + event.text! }
                  : m
              )
            );
          } else if (event.type === "citations" && event.citations) {
            citations = event.citations;
          } else if (event.type === "done") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      isStreaming: false,
                      citations,
                      queryType: event.query_type,
                    }
                  : m
              )
            );
          } else if (event.type === "error") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      content: `Error: ${event.message}`,
                      isStreaming: false,
                    }
                  : m
              )
            );
          }
        }
      } catch (err) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: `Failed to get response. ${err instanceof Error ? err.message : ""}`,
                  isStreaming: false,
                }
              : m
          )
        );
      } finally {
        setIsLoading(false);
      }
    },
    [messages, isLoading, sessionId]
  );

  const clearMessages = useCallback(() => setMessages([]), []);

  return { messages, isLoading, sendMessage, clearMessages, sessionId };
}
