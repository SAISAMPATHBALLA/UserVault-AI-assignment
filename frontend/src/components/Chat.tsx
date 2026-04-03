/// <reference types="vite/client" />
import React, { useEffect, useRef, useState, useCallback } from "react";
import { Loader } from "rsuite";
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
  const wsRef      = useRef<WebSocket | null>(null);
  const bottomRef  = useRef<HTMLDivElement | null>(null);
  const inputRef   = useRef<HTMLTextAreaElement | null>(null);
  const firstMsgSent = useRef(false);

  useEffect(() => {
    firstMsgSent.current = false;
    setStatus(null);
    setHistoryLoading(true);

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

    const ws = new WebSocket(`${WS_BASE}/ws/chat/${sessionId}`);
    wsRef.current = ws;

    ws.onopen  = () => { setConnected(true); inputRef.current?.focus(); };
    ws.onclose = () => { setConnected(false); setStatus(null); };
    ws.onerror = () => setStatus("Connection error…");

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

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, status]);

  const addMsg = (partial: Partial<ChatMsg>) =>
    setMsgs(prev => [...prev, { id: crypto.randomUUID(), kind: "message", ...partial } as ChatMsg]);

  const newMsg = (role: MessageRole, content: string, isStreaming = false): ChatMsg => ({
    id: crypto.randomUUID(), kind: "message", role, content, isStreaming,
  });

  const wsSend = useCallback((obj: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify(obj));
  }, []);

  const submitQuestion = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || status || !connected) return;
    if (!firstMsgSent.current) { firstMsgSent.current = true; onFirstMessage(trimmed); }
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
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitQuestion(input); }
  };

  const isIdle = connected && !status;

  return (
    <div style={CONTAINER}>
      {/* Header */}
      <div style={HEADER}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15, color: "#0f172a", letterSpacing: "-.01em" }}>
            Developer Analytics
          </div>
          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 1 }}>
            {userProfile.name} · Org {userProfile.organization_id}
          </div>
        </div>
        <div style={STATUS_PILL} data-live={connected}>
          <span style={{
            width: 6, height: 6, borderRadius: "50%",
            background: connected ? "#22c55e" : "#94a3b8",
            display: "inline-block",
          }} />
          <span style={{ fontSize: 11, fontWeight: 600, color: connected ? "#16a34a" : "#94a3b8" }}>
            {connected ? "Live" : "Offline"}
          </span>
        </div>
      </div>

      {/* Messages */}
      <div style={MESSAGES_AREA}>
        {historyLoading ? (
          <div style={CENTER}>
            <Loader size="md" content="Loading conversation…" vertical />
          </div>
        ) : msgs.length === 0 && !status ? (
          <div style={CENTER}>
            <div style={WELCOME_ICON}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="1.5">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
              </svg>
            </div>
            <p style={{ color: "#334155", fontSize: 15, fontWeight: 600, margin: "0 0 6px" }}>
              What would you like to know?
            </p>
            <p style={{ color: "#94a3b8", fontSize: 13, maxWidth: 340, textAlign: "center", margin: 0 }}>
              Ask about your commits, pull request activity, code reviews, or performance scores.
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
            <span style={{ fontSize: 12, color: "#64748b" }}>{status}</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div style={INPUT_AREA}>
        <div style={INPUT_WRAPPER}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isIdle ? "Ask about your data…" : status ? "Processing…" : "Connecting…"}
            disabled={!isIdle}
            rows={1}
            style={{
              ...TEXTAREA,
              background: isIdle ? "#fff" : "#f8fafc",
              color: isIdle ? "#0f172a" : "#94a3b8",
            }}
          />
          <button
            onClick={() => submitQuestion(input)}
            disabled={!isIdle || !input.trim()}
            style={{
              ...SEND_BTN,
              background: isIdle && input.trim()
                ? "linear-gradient(135deg, #4f46e5, #6366f1)"
                : "#e2e8f0",
              color: isIdle && input.trim() ? "#fff" : "#94a3b8",
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
            </svg>
          </button>
        </div>
        <div style={{ fontSize: 11, color: "#cbd5e1", textAlign: "center", marginTop: 6 }}>
          Enter to send · Shift+Enter for new line
        </div>
      </div>
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────────
const CONTAINER: React.CSSProperties = {
  flex: 1, display: "flex", flexDirection: "column",
  height: "100vh", background: "#f8fafc", overflow: "hidden",
};
const HEADER: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "center",
  padding: "14px 28px", background: "#fff",
  borderBottom: "1px solid #e2e8f0",
  flexShrink: 0, boxShadow: "0 1px 3px rgba(0,0,0,.04)",
};
const STATUS_PILL: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 5,
  background: "#f8fafc", border: "1px solid #e2e8f0",
  borderRadius: 20, padding: "4px 10px",
};
const MESSAGES_AREA: React.CSSProperties = {
  flex: 1, overflowY: "auto", padding: "24px 28px",
  display: "flex", flexDirection: "column", gap: 4,
};
const CENTER: React.CSSProperties = {
  flex: 1, display: "flex", flexDirection: "column",
  alignItems: "center", justifyContent: "center", padding: "60px 0",
};
const WELCOME_ICON: React.CSSProperties = {
  width: 64, height: 64, borderRadius: "50%",
  background: "linear-gradient(135deg, rgba(79,70,229,.08), rgba(99,102,241,.12))",
  display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16,
};
const STATUS_ROW: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 8, padding: "8px 0",
};
const INPUT_AREA: React.CSSProperties = {
  padding: "14px 28px 16px",
  background: "#fff", borderTop: "1px solid #e2e8f0",
  flexShrink: 0, boxShadow: "0 -1px 6px rgba(0,0,0,.04)",
};
const INPUT_WRAPPER: React.CSSProperties = {
  display: "flex", alignItems: "flex-end", gap: 10,
  background: "#fff", border: "1.5px solid #e2e8f0",
  borderRadius: 14, padding: "10px 10px 10px 16px",
  boxShadow: "0 1px 4px rgba(0,0,0,.04)",
};
const TEXTAREA: React.CSSProperties = {
  flex: 1, border: "none", outline: "none", resize: "none",
  fontSize: 14, lineHeight: 1.6, fontFamily: "inherit",
  maxHeight: 120, overflowY: "auto",
};
const SEND_BTN: React.CSSProperties = {
  width: 36, height: 36, borderRadius: 10, border: "none",
  display: "flex", alignItems: "center", justifyContent: "center",
  cursor: "pointer", flexShrink: 0, transition: "background .15s",
};
