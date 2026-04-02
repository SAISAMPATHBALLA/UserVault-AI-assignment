/// <reference types="vite/client"/>
import React, { useEffect, useRef, useState, useCallback } from "react";
import { Loader } from "rsuite";
import Message, { MessageType } from "./Message";
import ReconstructedQuery from "./ReconstructedQuery";

interface ChatMessage {
  id: string;
  type: "message" | "reconstructed";
  role?: MessageType;
  content?: string;
  isStreaming?: boolean;
  original?: string;
  reconstructed?: string;
}

interface Props {
  sessionId: string;
  userProfile: Record<string, unknown>;
}

const WS_BASE = import.meta.env.VITE_WS_URL || "ws://localhost:8000";

const Chat: React.FC<Props> = ({ sessionId, userProfile }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const send = useCallback((obj: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(obj));
    }
  }, []);

  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws/chat/${sessionId}`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);

    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);

      if (msg.type === "status") {
        setStatus(msg.message);

      } else if (msg.type === "reconstructed_query") {
        setStatus("Waiting for your confirmation...");
        setMessages(prev => [
          ...prev,
          { id: crypto.randomUUID(), type: "reconstructed", original: msg.original, reconstructed: msg.query }
        ]);

      } else if (msg.type === "rejected") {
        setStatus(null);
        setMessages(prev => [
          ...prev,
          { id: crypto.randomUUID(), type: "message", role: "rejected", content: msg.reason }
        ]);

      } else if (msg.type === "followup") {
        setStatus(null);
        setMessages(prev => [
          ...prev,
          { id: crypto.randomUUID(), type: "message", role: "followup", content: msg.message }
        ]);

      } else if (msg.type === "token") {
        setStatus(null);
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.isStreaming) {
            return [
              ...prev.slice(0, -1),
              { ...last, content: (last.content || "") + msg.content }
            ];
          }
          return [
            ...prev,
            { id: crypto.randomUUID(), type: "message", role: "assistant", content: msg.content, isStreaming: true }
          ];
        });

      } else if (msg.type === "done") {
        setStatus(null);
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last?.isStreaming) {
            return [...prev.slice(0, -1), { ...last, isStreaming: false }];
          }
          return prev;
        });

      } else if (msg.type === "error") {
        setStatus(null);
        setMessages(prev => [
          ...prev,
          { id: crypto.randomUUID(), type: "message", role: "error", content: msg.message }
        ]);
      }
    };

    return () => ws.close();
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const submitQuestion = (text: string) => {
    if (!text.trim()) return;
    setMessages(prev => [
      ...prev,
      { id: crypto.randomUUID(), type: "message", role: "user", content: text }
    ]);
    send({ type: "question", text, user_profile: userProfile });
    setInput("");
  };

  const handleStop = () => {
    send({ type: "stop" });
    setStatus(null);
    setMessages(prev => prev.filter(m => m.type !== "reconstructed"));
  };

  const handleEdit = (corrected: string) => {
    setMessages(prev => prev.filter(m => m.type !== "reconstructed"));
    setMessages(prev => [
      ...prev,
      { id: crypto.randomUUID(), type: "message", role: "user", content: `[Edited] ${corrected}` }
    ]);
    send({ type: "edit", query: corrected, user_profile: userProfile });
  };

  return (
    <div style={CONTAINER}>
      <div style={STATUS_BAR}>
        <span style={{ color: connected ? "#4CAF50" : "#f44336", fontSize: 12 }}>
          {connected ? "● Connected" : "○ Disconnected"}
        </span>
        <span style={{ fontSize: 12, color: "#888" }}>Session: {sessionId.slice(0, 8)}…</span>
      </div>

      <div style={MESSAGES}>
        {messages.map(m =>
          m.type === "reconstructed" ? (
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
          <div style={STATUS_LOADER}>
            <Loader speed="fast" content={status} />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div style={INPUT_ROW}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !e.shiftKey && !status && submitQuestion(input)}
          placeholder={status ? "Processing…" : "Ask a question about the data…"}
          style={{ ...INPUT, background: status ? "#f9f9f9" : "#fff" }}
          disabled={!connected || !!status}
        />
        <button style={SEND_BTN} onClick={() => submitQuestion(input)} disabled={!connected || !input.trim() || !!status}>
          Send
        </button>
      </div>
    </div>
  );
};

const CONTAINER: React.CSSProperties = {
  display: "flex", flexDirection: "column", height: "100vh", flex: 1, background: "#fff",
};
const STATUS_BAR: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", padding: "6px 16px",
  background: "#fafafa", borderBottom: "1px solid #eee",
};
const MESSAGES: React.CSSProperties = {
  flex: 1, overflowY: "auto", padding: "16px", display: "flex",
  flexDirection: "column", gap: 4,
};
const INPUT_ROW: React.CSSProperties = {
  display: "flex", gap: 8, padding: "12px 16px", borderTop: "1px solid #eee",
};
const STATUS_LOADER: React.CSSProperties = {
  padding: "10px 4px", display: "flex", alignItems: "center",
};
const INPUT: React.CSSProperties = {
  flex: 1, padding: "10px 14px", borderRadius: 8, border: "1px solid #ddd",
  fontSize: 14, outline: "none",
};
const SEND_BTN: React.CSSProperties = {
  padding: "10px 20px", background: "#2196F3", color: "#fff", border: "none",
  borderRadius: 8, cursor: "pointer", fontWeight: 600, fontSize: 14,
};

export default Chat;
