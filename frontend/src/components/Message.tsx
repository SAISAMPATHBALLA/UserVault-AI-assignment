import type React from "react";

export type MessageRole = "user" | "assistant" | "rejected" | "followup" | "error";

interface Props {
  role: MessageRole;
  content: string;
  isStreaming?: boolean;
}

export default function Message({ role, content, isStreaming }: Props) {
  if (role === "user") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 4 }}>
        <div style={USER_BUBBLE}>{content}</div>
      </div>
    );
  }

  if (role === "assistant") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-start", gap: 10, marginBottom: 4, alignItems: "flex-start" }}>
        <div style={AI_AVATAR}>AI</div>
        <div style={ASSISTANT_CARD}>
          <div style={{ fontSize: 14, lineHeight: 1.7, color: "#1e293b", whiteSpace: "pre-wrap" }}>
            {content}
            {isStreaming && <span style={CURSOR} />}
          </div>
        </div>
      </div>
    );
  }

  // error, rejected, followup
  const cfg = INFO_CONFIG[role];
  return (
    <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 4 }}>
      <div style={{ ...INFO_BOX, borderLeft: `3px solid ${cfg.border}`, background: cfg.bg }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: cfg.labelColor, textTransform: "uppercase", letterSpacing: ".05em" }}>
          {cfg.label}
        </span>
        <span style={{ fontSize: 13, color: "#374151", lineHeight: 1.6 }}>{content}</span>
      </div>
    </div>
  );
}

const INFO_CONFIG = {
  rejected: { bg: "#fff1f2", border: "#fda4af", label: "Blocked",              labelColor: "#be123c" },
  followup: { bg: "#fefce8", border: "#fde047", label: "Clarification Needed", labelColor: "#92400e" },
  error:    { bg: "#fffbeb", border: "#fcd34d", label: "Notice",               labelColor: "#b45309" },
} as const;

const USER_BUBBLE: React.CSSProperties = {
  maxWidth: "70%",
  background: "linear-gradient(135deg, #4f46e5, #6366f1)",
  color: "#fff",
  borderRadius: "18px 18px 4px 18px",
  padding: "10px 16px",
  fontSize: 14,
  lineHeight: 1.65,
  whiteSpace: "pre-wrap",
  boxShadow: "0 2px 8px rgba(99,102,241,.25)",
};
const AI_AVATAR: React.CSSProperties = {
  width: 28, height: 28, borderRadius: "50%",
  background: "linear-gradient(135deg, #0ea5e9, #6366f1)",
  color: "#fff", fontSize: 10, fontWeight: 800,
  display: "flex", alignItems: "center", justifyContent: "center",
  flexShrink: 0, marginTop: 2,
};
const ASSISTANT_CARD: React.CSSProperties = {
  maxWidth: "70%",
  background: "#fff",
  border: "1px solid #e2e8f0",
  borderRadius: "4px 18px 18px 18px",
  padding: "12px 16px",
  boxShadow: "0 1px 4px rgba(0,0,0,.06)",
};
const INFO_BOX: React.CSSProperties = {
  maxWidth: "80%",
  borderRadius: 8,
  padding: "10px 14px",
  display: "flex",
  flexDirection: "column",
  gap: 4,
};
const CURSOR: React.CSSProperties = {
  display: "inline-block", width: 2, height: "1em",
  background: "#6366f1", marginLeft: 2, verticalAlign: "text-bottom",
  animation: "blink 1s step-end infinite",
};
