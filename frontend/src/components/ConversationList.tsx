import React from "react";
import type { Conversation } from "../App";

interface Props {
  conversations: Conversation[];
  activeSessionId: string | null;
  userName: string;
  onSelect: (sid: string) => void;
  onDelete: (sid: string) => void;
  onNew: () => void;
  onLogout: () => void;
  isCreating: boolean;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)  return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function ConversationList({
  conversations, activeSessionId, userName,
  onSelect, onDelete, onNew, onLogout, isCreating,
}: Props) {
  return (
    <div style={SIDEBAR}>
      {/* Branding */}
      <div style={BRAND}>
        <span style={{ fontSize: 18 }}>📊</span>
        <span style={{ fontWeight: 700, fontSize: 14, color: "#fff" }}>Dev Analytics</span>
      </div>

      {/* New chat button */}
      <button style={{ ...NEW_BTN, opacity: isCreating ? 0.7 : 1 }}
        onClick={onNew} disabled={isCreating}>
        {isCreating ? "Creating…" : "+ New Chat"}
      </button>

      {/* Conversation list */}
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 2 }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: "#6b7280", padding: "8px 10px 4px",
          textTransform: "uppercase", letterSpacing: ".06em" }}>
          Recent
        </div>
        {conversations.map(c => (
          <div key={c.session_id} style={{
            ...ITEM, background: c.session_id === activeSessionId ? "#1e2a3a" : "transparent",
          }}>
            <div style={{ flex: 1, cursor: "pointer", overflow: "hidden" }} onClick={() => onSelect(c.session_id)}>
              <div style={{ fontSize: 13, fontWeight: 500, color: "#e2e8f0",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {c.title}
              </div>
              <div style={{ fontSize: 11, color: "#6b7280", marginTop: 2 }}>
                {timeAgo(c.created_at)}
              </div>
            </div>
            <button title="Delete" style={DEL_BTN}
              onClick={e => { e.stopPropagation(); onDelete(c.session_id); }}>
              ✕
            </button>
          </div>
        ))}
        {conversations.length === 0 && (
          <div style={{ color: "#4b5563", fontSize: 13, padding: "12px 10px" }}>
            No conversations yet
          </div>
        )}
      </div>

      {/* User footer */}
      <div style={FOOTER}>
        <div style={{ overflow: "hidden" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#e2e8f0",
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {userName}
          </div>
          <div style={{ fontSize: 11, color: "#6b7280" }}>Signed in</div>
        </div>
        <button style={LOGOUT_BTN} onClick={onLogout} title="Sign out">⇠</button>
      </div>
    </div>
  );
}

const SIDEBAR: React.CSSProperties = {
  width: 240, background: "#111827",
  display: "flex", flexDirection: "column",
  padding: "12px 10px", gap: 8,
  height: "100vh", flexShrink: 0,
};
const BRAND: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 8,
  padding: "4px 6px 10px", borderBottom: "1px solid #1f2937",
};
const NEW_BTN: React.CSSProperties = {
  padding: "9px 12px", background: "#4f46e5", color: "#fff",
  border: "none", borderRadius: 8, cursor: "pointer",
  fontWeight: 600, fontSize: 13, textAlign: "left",
  transition: "opacity .15s",
};
const ITEM: React.CSSProperties = {
  display: "flex", alignItems: "center", padding: "8px 8px",
  borderRadius: 7, gap: 6, transition: "background .1s",
};
const DEL_BTN: React.CSSProperties = {
  background: "none", border: "none", cursor: "pointer",
  color: "#4b5563", fontSize: 12, padding: "2px 5px",
  borderRadius: 4, flexShrink: 0,
  transition: "color .1s",
};
const FOOTER: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 8,
  padding: "10px 6px 4px", borderTop: "1px solid #1f2937",
};
const LOGOUT_BTN: React.CSSProperties = {
  background: "none", border: "1px solid #374151", cursor: "pointer",
  color: "#6b7280", fontSize: 14, padding: "4px 8px",
  borderRadius: 6, flexShrink: 0,
};
