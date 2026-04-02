import React from "react";
import { Button, Divider, Loader } from "rsuite";
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
        <span style={{ fontSize: 20 }}>📊</span>
        <span style={{ fontWeight: 700, fontSize: 14, color: "#fff", letterSpacing: ".01em" }}>
          Dev Analytics
        </span>
      </div>

      {/* New chat button */}
      <Button
        appearance="primary"
        block
        onClick={onNew}
        disabled={isCreating}
        style={{ borderRadius: 8, fontWeight: 600, fontSize: 13 }}
      >
        {isCreating ? <><Loader size="xs" style={{ marginRight: 6 }} />Creating…</> : "+ New Chat"}
      </Button>

      <Divider style={{ margin: "8px 0", borderColor: "#1f2937" }} />

      {/* Conversation list */}
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 2 }}>
        <div style={SECTION_LABEL}>Recent</div>
        {conversations.map(c => (
          <div
            key={c.session_id}
            style={{
              ...ITEM,
              background: c.session_id === activeSessionId ? "#1e3a5f" : "transparent",
              borderLeft: c.session_id === activeSessionId ? "3px solid #3b82f6" : "3px solid transparent",
            }}
          >
            <div
              style={{ flex: 1, cursor: "pointer", overflow: "hidden", minWidth: 0 }}
              onClick={() => onSelect(c.session_id)}
            >
              <div style={ITEM_TITLE}>{c.title}</div>
              <div style={ITEM_TIME}>{timeAgo(c.created_at)}</div>
            </div>
            <button
              title="Delete"
              style={DEL_BTN}
              onClick={e => { e.stopPropagation(); onDelete(c.session_id); }}
            >
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

      <Divider style={{ margin: "8px 0", borderColor: "#1f2937" }} />

      {/* User footer */}
      <div style={FOOTER}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, overflow: "hidden" }}>
          <div style={AVATAR}>{userName.charAt(0).toUpperCase()}</div>
          <div style={{ overflow: "hidden" }}>
            <div style={FOOTER_NAME}>{userName}</div>
            <div style={{ fontSize: 11, color: "#6b7280" }}>Signed in</div>
          </div>
        </div>
        <Button
          appearance="subtle"
          size="xs"
          onClick={onLogout}
          title="Sign out"
          style={{ color: "#6b7280", padding: "4px 8px", flexShrink: 0 }}
        >
          Sign out
        </Button>
      </div>
    </div>
  );
}

const SIDEBAR: React.CSSProperties = {
  width: 256,
  background: "#0f172a",
  display: "flex",
  flexDirection: "column",
  padding: "16px 12px",
  gap: 8,
  height: "100vh",
  flexShrink: 0,
  boxSizing: "border-box",
};
const BRAND: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  padding: "4px 4px 12px",
};
const SECTION_LABEL: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 700,
  color: "#475569",
  padding: "4px 8px",
  textTransform: "uppercase",
  letterSpacing: ".08em",
};
const ITEM: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  padding: "8px 10px",
  borderRadius: 8,
  gap: 6,
  transition: "background .12s",
  cursor: "default",
};
const ITEM_TITLE: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 500,
  color: "#e2e8f0",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};
const ITEM_TIME: React.CSSProperties = {
  fontSize: 11,
  color: "#64748b",
  marginTop: 2,
};
const DEL_BTN: React.CSSProperties = {
  background: "none",
  border: "none",
  cursor: "pointer",
  color: "#475569",
  fontSize: 11,
  padding: "3px 6px",
  borderRadius: 4,
  flexShrink: 0,
  transition: "color .1s",
};
const FOOTER: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  padding: "4px 4px",
};
const FOOTER_NAME: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: "#e2e8f0",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};
const AVATAR: React.CSSProperties = {
  width: 28,
  height: 28,
  borderRadius: "50%",
  background: "#3b82f6",
  color: "#fff",
  fontSize: 13,
  fontWeight: 700,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  flexShrink: 0,
};
