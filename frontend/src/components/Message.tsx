import React from "react";

export type MessageType = "user" | "assistant" | "rejected" | "followup" | "meta" | "error";

export interface MessageProps {
  role: MessageType;
  content: string;
  reconstructedQuery?: string;
  onStop?: () => void;
  onEdit?: (q: string) => void;
  isStreaming?: boolean;
}

const STYLE: Record<MessageType, React.CSSProperties> = {
  user:       { background: "#e8f4fd", alignSelf: "flex-end",  borderLeft: "4px solid #2196F3" },
  assistant:  { background: "#f9f9f9", alignSelf: "flex-start", borderLeft: "4px solid #4CAF50" },
  rejected:   { background: "#fff0f0", alignSelf: "flex-start", borderLeft: "4px solid #f44336" },
  followup:   { background: "#fffde7", alignSelf: "flex-start", borderLeft: "4px solid #FFC107" },
  meta:       { background: "#f3e5f5", alignSelf: "flex-start", borderLeft: "4px solid #9C27B0" },
  error:      { background: "#fce4ec", alignSelf: "flex-start", borderLeft: "4px solid #E91E63" },
};

const LABEL: Record<MessageType, string> = {
  user:      "You",
  assistant: "Assistant",
  rejected:  "Blocked",
  followup:  "Clarification needed",
  meta:      "Schema info",
  error:     "Error",
};

export const Message: React.FC<MessageProps> = ({ role, content, isStreaming }) => (
  <div style={{ ...BASE, ...STYLE[role] }}>
    <span style={{ fontSize: 11, fontWeight: 700, color: "#666", marginBottom: 4, display: "block" }}>
      {LABEL[role]}
    </span>
    <span style={{ whiteSpace: "pre-wrap", fontSize: 14 }}>
      {content}
      {isStreaming && <span style={{ animation: "blink 1s step-end infinite" }}>▌</span>}
    </span>
  </div>
);

const BASE: React.CSSProperties = {
  padding: "10px 14px",
  borderRadius: 8,
  maxWidth: "78%",
  margin: "4px 0",
  boxShadow: "0 1px 3px rgba(0,0,0,.08)",
};

export default Message;
