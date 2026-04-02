import React from "react";

interface Conversation {
  session_id: string;
  title?: string;
  created_at: string;
}

interface Props {
  conversations: Conversation[];
  activeSessionId: string;
  onSelect: (sessionId: string) => void;
  onDelete: (sessionId: string) => void;
  onNew: () => void;
}

const ConversationList: React.FC<Props> = ({
  conversations, activeSessionId, onSelect, onDelete, onNew
}) => (
  <div style={SIDEBAR}>
    <button style={NEW_BTN} onClick={onNew}>+ New Chat</button>
    <div style={{ overflowY: "auto", flex: 1 }}>
      {conversations.map(c => (
        <div
          key={c.session_id}
          style={{ ...ITEM, background: c.session_id === activeSessionId ? "#e8f4fd" : "transparent" }}
        >
          <div style={{ flex: 1, cursor: "pointer" }} onClick={() => onSelect(c.session_id)}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#333" }}>
              {c.title || "Conversation"}
            </div>
            <div style={{ fontSize: 11, color: "#999" }}>
              {new Date(c.created_at).toLocaleDateString()}
            </div>
          </div>
          <button
            style={DEL_BTN}
            onClick={e => { e.stopPropagation(); onDelete(c.session_id); }}
            title="Delete"
          >
            ✕
          </button>
        </div>
      ))}
      {conversations.length === 0 && (
        <div style={{ color: "#aaa", fontSize: 13, padding: "12px 8px" }}>No conversations yet</div>
      )}
    </div>
  </div>
);

const SIDEBAR: React.CSSProperties = {
  width: 220, background: "#f7f7f7", borderRight: "1px solid #e0e0e0",
  display: "flex", flexDirection: "column", padding: "12px 8px", gap: 4, height: "100vh",
};
const NEW_BTN: React.CSSProperties = {
  padding: "8px 12px", background: "#2196F3", color: "#fff", border: "none",
  borderRadius: 6, cursor: "pointer", fontWeight: 600, marginBottom: 8,
};
const ITEM: React.CSSProperties = {
  display: "flex", alignItems: "center", padding: "8px 6px",
  borderRadius: 6, gap: 6,
};
const DEL_BTN: React.CSSProperties = {
  background: "none", border: "none", cursor: "pointer", color: "#bbb",
  fontSize: 13, padding: "2px 5px", borderRadius: 4,
};

export default ConversationList;
