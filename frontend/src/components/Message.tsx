import type { CSSProperties } from "react";

export type MessageRole = "user" | "assistant" | "rejected" | "followup" | "error";

interface Props {
  role: MessageRole;
  content: string;
  isStreaming?: boolean;
}

const CONFIG: Record<MessageRole, { bg: string; border: string; label: string; align: CSSProperties["justifyContent"] }> = {
  user:      { bg: "#eff6ff", border: "#3b82f6", label: "You",                 align: "flex-end"   },
  assistant: { bg: "#f0fdf4", border: "#22c55e", label: "Analytics Assistant", align: "flex-start" },
  rejected:  { bg: "#fff1f2", border: "#f43f5e", label: "Blocked",             align: "flex-start" },
  followup:  { bg: "#fefce8", border: "#eab308", label: "Clarification needed",align: "flex-start" },
  error:     { bg: "#fef3c7", border: "#f59e0b", label: "Notice",              align: "flex-start" },
};

export default function Message({ role, content, isStreaming }: Props) {
  const cfg = CONFIG[role];
  return (
    <div style={{ display: "flex", justifyContent: cfg.align, animation: "fadeIn .2s ease" }}>
      <div style={{
        maxWidth: "76%", padding: "10px 14px", borderRadius: 12,
        background: cfg.bg, borderLeft: `3px solid ${cfg.border}`,
        boxShadow: "0 1px 4px rgba(0,0,0,.06)",
        animation: "fadeIn .2s ease",
      }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: "#6b7280", marginBottom: 5, textTransform: "uppercase", letterSpacing: ".04em" }}>
          {cfg.label}
        </div>
        <div style={{ fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap", color: "#1f2937" }}>
          {content}
          {isStreaming && (
            <span style={{ display: "inline-block", width: 2, height: "1em",
              background: "#4f46e5", marginLeft: 2, verticalAlign: "text-bottom",
              animation: "blink 1s step-end infinite" }} />
          )}
        </div>
      </div>
    </div>
  );
}
