import type { CSSProperties } from "react";
import { Panel } from "rsuite";

export type MessageRole = "user" | "assistant" | "rejected" | "followup" | "error";

interface Props {
  role: MessageRole;
  content: string;
  isStreaming?: boolean;
}

const CONFIG: Record<MessageRole, {
  bg: string; border: string; label: string;
  align: CSSProperties["justifyContent"]; labelColor: string;
}> = {
  user:      { bg: "#eff6ff", border: "#3b82f6", label: "You",                  align: "flex-end",   labelColor: "#2563eb" },
  assistant: { bg: "#f0fdf4", border: "#22c55e", label: "Analytics Assistant",  align: "flex-start", labelColor: "#16a34a" },
  rejected:  { bg: "#fff1f2", border: "#f43f5e", label: "Blocked",              align: "flex-start", labelColor: "#e11d48" },
  followup:  { bg: "#fefce8", border: "#eab308", label: "Clarification needed", align: "flex-start", labelColor: "#b45309" },
  error:     { bg: "#fef3c7", border: "#f59e0b", label: "Notice",               align: "flex-start", labelColor: "#d97706" },
};

export default function Message({ role, content, isStreaming }: Props) {
  const cfg = CONFIG[role];
  return (
    <div style={{ display: "flex", justifyContent: cfg.align, animation: "fadeIn .2s ease" }}>
      <Panel
        style={{
          maxWidth: "76%",
          background: cfg.bg,
          borderLeft: `3px solid ${cfg.border}`,
          borderRadius: 12,
          padding: "10px 14px",
          boxShadow: "0 1px 4px rgba(0,0,0,.06)",
        }}
      >
        <div style={{
          fontSize: 11, fontWeight: 700, color: cfg.labelColor,
          marginBottom: 5, textTransform: "uppercase", letterSpacing: ".04em",
        }}>
          {cfg.label}
        </div>
        <div style={{ fontSize: 14, lineHeight: 1.65, whiteSpace: "pre-wrap", color: "#1e293b" }}>
          {content}
          {isStreaming && (
            <span style={{
              display: "inline-block", width: 2, height: "1em",
              background: "#4f46e5", marginLeft: 2, verticalAlign: "text-bottom",
              animation: "blink 1s step-end infinite",
            }} />
          )}
        </div>
      </Panel>
    </div>
  );
}
