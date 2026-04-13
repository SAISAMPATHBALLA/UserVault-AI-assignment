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
          <div style={{ fontSize: 14, lineHeight: 1.7, color: "#d0d0d0", whiteSpace: "pre-wrap" }}>
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
        <span style={{ fontSize: 13, color: "#b0b0b0", lineHeight: 1.6 }}>{content}</span>
      </div>
    </div>
  );
}

const INFO_CONFIG = {
  rejected: { bg: "rgba(220,38,38,0.08)",   border: "#ef4444", label: "Blocked",              labelColor: "#f87171" },
  followup: { bg: "rgba(234,179,8,0.08)",   border: "#eab308", label: "Clarification Needed", labelColor: "#facc15" },
  error:    { bg: "rgba(245,158,11,0.08)",  border: "#f59e0b", label: "Notice",               labelColor: "#fbbf24" },
} as const;

const USER_BUBBLE: React.CSSProperties = {
  maxWidth: "70%",
  background: "linear-gradient(135deg, #7c3aed, #6d28d9)",
  color: "#fff",
  borderRadius: "18px 18px 4px 18px",
  padding: "10px 16px",
  fontSize: 14,
  lineHeight: 1.65,
  whiteSpace: "pre-wrap",
  boxShadow: "0 2px 8px rgba(139,92,246,.3)",
};
const AI_AVATAR: React.CSSProperties = {
  width: 28, height: 28, borderRadius: "50%",
  background: "linear-gradient(135deg, #7c3aed, #6d28d9)",
  color: "#fff", fontSize: 10, fontWeight: 800,
  display: "flex", alignItems: "center", justifyContent: "center",
  flexShrink: 0, marginTop: 2,
};
const ASSISTANT_CARD: React.CSSProperties = {
  maxWidth: "70%",
  background: "#0f0f0f",
  border: "1px solid rgba(139,92,246,0.2)",
  borderRadius: "4px 18px 18px 18px",
  padding: "12px 16px",
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
  background: "#8b5cf6", marginLeft: 2, verticalAlign: "text-bottom",
  animation: "blink 1s step-end infinite",
};
