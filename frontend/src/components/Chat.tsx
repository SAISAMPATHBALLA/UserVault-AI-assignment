/// <reference types="vite/client" />
import React, { useEffect, useRef, useState, useCallback } from "react";
import { Button, Input, Loader, Tag } from "rsuite";
import Message, { MessageRole } from "./Message";
import ReconstructedQuery from "./ReconstructedQuery";
import type { UserProfile } from "../App";

interface ChatMsg {
  id: string;
  kind: "message" | "reconstructed";
  role?: MessageRole;
  content?: string;
  isStreaming?: boolean;
  original?: string;
  reconstructed?: string;
}

interface Props {
  sessionId: string;
  userProfile: UserProfile;
  onFirstMessage: (text: string) => void;
}

const WS_BASE  = import.meta.env.VITE_WS_URL  || "ws://localhost:8000";
const API_BASE = import.meta.env.VITE_API_URL  || "http://localhost:8000";

export default function Chat({ sessionId, userProfile, onFirstMessage }: Props) {
  const [msgs, setMsgs]           = useState<ChatMsg[]>([]);
  const [input, setInput]         = useState("");
  const [connected, setConnected] = useState(false);
  const [status, setStatus]       = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(true);
  const wsRef                     = useRef<WebSocket | null>(null);
  const bottomRef                 = useRef<HTMLDivElement | null>(null);
  const firstMsgSent              = useRef(false);
  const inputRef                  = useRef<HTMLTextAreaElement | null>(null);

  // Load chat history then open WebSocket
  useEffect(() => {
    firstMsgSent.current = false;
    setStatus(null);
    setHistoryLoading(true);

    // Fetch persisted messages first
    fetch(`${API_BASE}/api/messages/${sessionId}`)
      .then(r => r.json())
      .then((data: { messages: Array<{ role: string; content: string }> }) => {
        const history: ChatMsg[] = (data.messages || []).map(m => ({
          id: crypto.randomUUID(),
          kind: "message",
          role: m.role as MessageRole,
          content: m.content,
          isStreaming: false,
        }));
        setMsgs(history);
        if (history.length > 0) firstMsgSent.current = true;
      })
      .catch(() => setMsgs([]))
      .finally(() => setHistoryLoading(false));

    // Open WebSocket
    const ws = new WebSocket(`${WS_BASE}/ws/chat/${sessionId}`);
    wsRef.current = ws;

    ws.onopen  = () => { setConnected(true); inputRef.current?.focus(); };
    ws.onclose = () => { setConnected(false); setStatus(null); };
    ws.onerror = () => setStatus("Connection error — reconnecting…");

    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data as string);

      switch (msg.type) {
        case "status":
          setStatus(msg.message);
          break;

        case "reconstructed_query":
          setStatus(null);
          addMsg({ kind: "reconstructed", original: msg.original, reconstructed: msg.query });
          break;

        case "token":
          setStatus(null);
          setMsgs(prev => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant" && last.isStreaming) {
              return [...prev.slice(0, -1), { ...last, content: (last.content ?? "") + msg.content }];
            }
            return [...prev, newMsg("assistant", msg.content, true)];
          });
          break;

        case "done":
          setStatus(null);
          setMsgs(prev => {
            const last = prev[prev.length - 1];
            return last?.isStreaming ? [...prev.slice(0, -1), { ...last, isStreaming: false }] : prev;
          });
          break;

        case "rejected":
          setStatus(null);
          addMsg({ kind: "message", role: "rejected", content: msg.reason });
          break;

        case "followup":
          setStatus(null);
          addMsg({ kind: "message", role: "followup", content: msg.message });
          break;

        case "error":
          setStatus(null);
          addMsg({ kind: "message", role: "error", content: msg.message });
          break;
      }
    };

    return () => ws.close();
  }, [sessionId]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, status]);

  const addMsg = (partial: Partial<ChatMsg>) => {
    setMsgs(prev => [...prev, { id: crypto.randomUUID(), kind: "message", ...partial } as ChatMsg]);
  };

  const newMsg = (role: MessageRole, content: string, isStreaming = false): ChatMsg => ({
    id: crypto.randomUUID(), kind: "message", role, content, isStreaming,
  });

  const wsSend = useCallback((obj: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(obj));
    }
  }, []);

  const submitQuestion = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || status || !connected) return;

    if (!firstMsgSent.current) {
      firstMsgSent.current = true;
      onFirstMessage(trimmed);
    }

    addMsg({ kind: "message", role: "user", content: trimmed });
    setInput("");
    setStatus("Understanding your question…");

    wsSend({ type: "question", text: trimmed, user_profile: userProfile });
  };

  const handleStop = () => {
    wsSend({ type: "stop" });
    setStatus(null);
    setMsgs(prev => prev.filter(m => m.kind !== "reconstructed"));
  };

  const handleEdit = (corrected: string) => {
    setMsgs(prev => prev.filter(m => m.kind !== "reconstructed"));
    addMsg({ kind: "message", role: "user", content: `↩ Edited: ${corrected}` });
    setStatus("Processing edited query…");
    wsSend({ type: "edit", query: corrected, user_profile: userProfile });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitQuestion(input);
    }
  };

  const isIdle = connected && !status;

  return (
    <div style={CONTAINER}>
      {/* Header */}
      <div style={HEADER}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontWeight: 700, fontSize: 15, color: "#0f172a" }}>Developer Analytics</span>
        </div>
        <Tag
          color={connected ? "green" : "red"}
          style={{ fontSize: 11, fontWeight: 600 }}
        >
          {connected ? "● Live" : "○ Offline"}
        </Tag>
      </div>

      {/* Messages */}
      <div style={MESSAGES_AREA}>
        {historyLoading ? (
          <div style={CENTER_PLACEHOLDER}>
            <Loader size="md" content="Loading conversation…" vertical />
          </div>
        ) : msgs.length === 0 && !status ? (
          <div style={CENTER_PLACEHOLDER}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>👋</div>
            <p style={{ color: "#64748b", fontSize: 14, textAlign: "center", maxWidth: 360 }}>
              Ask me about your commits, pull requests, code reviews, or performance scores.
            </p>
          </div>
        ) : null}

        {!historyLoading && msgs.map(m =>
          m.kind === "reconstructed" ? (
            <ReconstructedQuery
              key={m.id}
              original={m.original!}
              reconstructed={m.reconstructed!}
              onStop={handleStop}
              onEdit={handleEdit}
            />
          ) : (
            <Message key={m.id} role={m.role!} content={m.content!} isStreaming={m.isStreaming} />
          )
        )}

        {status && (
          <div style={STATUS_ROW}>
            <Loader size="xs" />
            <span style={{ fontSize: 13, color: "#64748b" }}>{status}</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={INPUT_AREA}>
        <Input
          as="textarea"
          ref={inputRef as React.Ref<HTMLTextAreaElement>}
          value={input}
          onChange={(val: string) => setInput(val)}
          onKeyDown={handleKeyDown}
          placeholder={
            isIdle
              ? "Ask about your data… (Enter to send, Shift+Enter for new line)"
              : status
              ? "Processing…"
              : "Connecting…"
          }
          disabled={!isIdle}
          rows={2}
          style={{
            flex: 1,
            borderRadius: 10,
            resize: "none",
            fontSize: 14,
            background: isIdle ? "#fff" : "#f8fafc",
          }}
        />
        <Button
          appearance="primary"
          onClick={() => submitQuestion(input)}
          disabled={!isIdle || !input.trim()}
          style={{ borderRadius: 10, fontWeight: 600, padding: "10px 24px", alignSelf: "flex-end" }}
        >
          Send
        </Button>
      </div>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────
const CONTAINER: React.CSSProperties = {
  flex: 1, display: "flex", flexDirection: "column",
  height: "100vh", background: "#fff", overflow: "hidden",
};
const HEADER: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "center",
  padding: "14px 24px", borderBottom: "1px solid #e2e8f0",
  background: "#fff", flexShrink: 0, boxShadow: "0 1px 3px rgba(0,0,0,.04)",
};
const MESSAGES_AREA: React.CSSProperties = {
  flex: 1, overflowY: "auto", padding: "20px 24px",
  display: "flex", flexDirection: "column", gap: 10,
};
const CENTER_PLACEHOLDER: React.CSSProperties = {
  flex: 1, display: "flex", flexDirection: "column",
  alignItems: "center", justifyContent: "center",
  padding: "40px 0",
};
const STATUS_ROW: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 8,
  padding: "6px 0", marginTop: 4,
};
const INPUT_AREA: React.CSSProperties = {
  display: "flex", gap: 10, padding: "14px 20px",
  borderTop: "1px solid #e2e8f0", background: "#fff", flexShrink: 0,
  alignItems: "flex-end", boxShadow: "0 -1px 4px rgba(0,0,0,.04)",
};
