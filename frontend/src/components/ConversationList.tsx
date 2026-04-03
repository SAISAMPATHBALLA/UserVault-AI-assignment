import React, { useState, useEffect } from "react";
import { Loader } from "rsuite";
import type { Conversation, UserProfile } from "../App";

const TIMEZONES = [
  "UTC", "Asia/Kolkata", "Asia/Singapore", "Asia/Tokyo",
  "America/New_York", "America/Los_Angeles", "America/Chicago",
  "Europe/London", "Europe/Berlin", "Europe/Paris", "Australia/Sydney",
];

interface Props {
  conversations: Conversation[];
  activeSessionId: string | null;
  profile: UserProfile | null;
  onSelect: (sid: string) => void;
  onDelete: (sid: string) => void;
  onNew: () => void;
  onProfileUpdate: (p: UserProfile) => Promise<void>;
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
  conversations, activeSessionId, profile,
  onSelect, onDelete, onNew, onProfileUpdate, isCreating,
}: Props) {
  const [showForm, setShowForm] = useState(!profile);
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState("");
  const [form, setForm] = useState({
    name:            profile?.name            ?? "",
    author_id:       profile?.author_id?.toString() ?? "",
    account_id:      profile?.account_id      ?? "",
    organization_id: profile?.organization_id?.toString() ?? "",
    team_id:         profile?.team_id?.toString() ?? "",
    timezone:        profile?.timezone        ?? "Asia/Kolkata",
  });

  // Sync form when profile is set externally (first save)
  useEffect(() => {
    if (profile) {
      setForm({
        name:            profile.name,
        author_id:       profile.author_id.toString(),
        account_id:      profile.account_id,
        organization_id: profile.organization_id.toString(),
        team_id:         profile.team_id?.toString() ?? "",
        timezone:        profile.timezone,
      });
    }
  }, [profile]);

  const set = (k: keyof typeof form) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm(prev => ({ ...prev, [k]: e.target.value }));

  const handleSave = async () => {
    setError("");
    if (!form.name.trim() || !form.author_id || !form.account_id || !form.organization_id) {
      setError("All fields except Team ID are required."); return;
    }
    const author_id = Number(form.author_id);
    const organization_id = Number(form.organization_id);
    const team_id = form.team_id ? Number(form.team_id) : null;
    if (!Number.isInteger(author_id) || author_id <= 0) {
      setError("Author ID must be a positive integer."); return;
    }
    if (!Number.isInteger(organization_id) || organization_id <= 0) {
      setError("Organization ID must be a positive integer."); return;
    }
    setSaving(true);
    try {
      await onProfileUpdate({
        name: form.name.trim(),
        author_id,
        account_id: form.account_id.trim(),
        organization_id,
        team_id,
        timezone: form.timezone,
      });
      setShowForm(false);
    } catch {
      setError("Failed to connect. Check your details and try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={SIDEBAR}>
      {/* Branding */}
      <div style={BRAND}>
        <div style={BRAND_ICON}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="2">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
          </svg>
        </div>
        <span style={{ fontWeight: 700, fontSize: 14, color: "#f8fafc", letterSpacing: ".01em" }}>
          Dev Analytics
        </span>
      </div>

      {/* New Chat button — only if profile is set */}
      {profile && (
        <button
          onClick={onNew}
          disabled={isCreating}
          style={NEW_BTN}
        >
          {isCreating
            ? <><Loader size="xs" style={{ marginRight: 6 }} />Creating…</>
            : <><span style={{ fontSize: 16, lineHeight: 1 }}>+</span>&nbsp; New Chat</>
          }
        </button>
      )}

      {/* Conversation list */}
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 2 }}>
        {conversations.length > 0 && (
          <div style={SECTION_LABEL}>Recent</div>
        )}
        {conversations.map(c => (
          <div
            key={c.session_id}
            style={{
              ...ITEM,
              background: c.session_id === activeSessionId ? "rgba(59,130,246,.15)" : "transparent",
              borderLeft: c.session_id === activeSessionId ? "2px solid #3b82f6" : "2px solid transparent",
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
        {!profile && conversations.length === 0 && (
          <div style={{ color: "#475569", fontSize: 12, padding: "12px 8px", lineHeight: 1.5 }}>
            Configure your profile below to start chatting.
          </div>
        )}
      </div>

      {/* Profile section */}
      <div style={PROFILE_SECTION}>
        <div style={DIVIDER} />

        {!showForm ? (
          /* Collapsed: show user info + edit toggle */
          <div style={PROFILE_ROW}>
            <div style={AVATAR}>{profile?.name.charAt(0).toUpperCase() ?? "?"}</div>
            <div style={{ flex: 1, overflow: "hidden" }}>
              <div style={PROFILE_NAME}>{profile?.name}</div>
              <div style={{ fontSize: 11, color: "#64748b" }}>ID: {profile?.author_id}</div>
            </div>
            <button
              title="Edit profile"
              style={ICON_BTN}
              onClick={() => setShowForm(true)}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            </button>
          </div>
        ) : (
          /* Expanded: profile form */
          <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
            <div style={FORM_HEADER}>
              <span style={{ color: "#94a3b8", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".08em" }}>
                {profile ? "Edit Profile" : "Set Up Profile"}
              </span>
              {profile && (
                <button style={ICON_BTN} onClick={() => { setShowForm(false); setError(""); }}>✕</button>
              )}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 340, overflowY: "auto", paddingRight: 2 }}>
              <Field label="Name *">
                <input style={INPUT} placeholder="Alex Kumar" value={form.name} onChange={set("name")} />
              </Field>
              <Field label="Author ID *">
                <input style={INPUT} type="number" placeholder="12345" value={form.author_id} onChange={set("author_id")} />
              </Field>
              <Field label="Account ID *">
                <input style={INPUT} placeholder="acc_abc123" value={form.account_id} onChange={set("account_id")} />
              </Field>
              <Field label="Organization ID *">
                <input style={INPUT} type="number" placeholder="67890" value={form.organization_id} onChange={set("organization_id")} />
              </Field>
              <Field label="Team ID (optional)">
                <input style={INPUT} type="number" placeholder="—" value={form.team_id} onChange={set("team_id")} />
              </Field>
              <Field label="Timezone">
                <select style={SELECT} value={form.timezone} onChange={set("timezone")}>
                  {TIMEZONES.map(tz => <option key={tz} value={tz}>{tz}</option>)}
                </select>
              </Field>
            </div>

            {error && (
              <div style={{ fontSize: 11, color: "#f87171", marginTop: 8, lineHeight: 1.4 }}>{error}</div>
            )}

            <button
              onClick={handleSave}
              disabled={saving}
              style={SAVE_BTN}
            >
              {saving ? "Connecting…" : profile ? "Save Changes" : "Start Chatting →"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: "#64748b", fontWeight: 600, marginBottom: 3, textTransform: "uppercase", letterSpacing: ".05em" }}>
        {label}
      </div>
      {children}
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────────
const SIDEBAR: React.CSSProperties = {
  width: 260,
  background: "#0f172a",
  display: "flex",
  flexDirection: "column",
  padding: "16px 12px",
  gap: 10,
  height: "100vh",
  flexShrink: 0,
  boxSizing: "border-box",
};
const BRAND: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 10, padding: "2px 4px 10px",
};
const BRAND_ICON: React.CSSProperties = {
  width: 28, height: 28, borderRadius: 8,
  background: "rgba(59,130,246,.15)",
  display: "flex", alignItems: "center", justifyContent: "center",
};
const NEW_BTN: React.CSSProperties = {
  display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
  background: "rgba(59,130,246,.12)", border: "1px solid rgba(59,130,246,.25)",
  color: "#60a5fa", borderRadius: 8, padding: "8px 12px", fontSize: 13,
  fontWeight: 600, cursor: "pointer", width: "100%",
};
const SECTION_LABEL: React.CSSProperties = {
  fontSize: 10, fontWeight: 700, color: "#334155",
  padding: "4px 8px", textTransform: "uppercase", letterSpacing: ".08em",
};
const ITEM: React.CSSProperties = {
  display: "flex", alignItems: "center",
  padding: "8px 10px", borderRadius: 8, gap: 6, cursor: "default",
};
const ITEM_TITLE: React.CSSProperties = {
  fontSize: 13, fontWeight: 500, color: "#cbd5e1",
  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
};
const ITEM_TIME: React.CSSProperties = { fontSize: 11, color: "#475569", marginTop: 2 };
const DEL_BTN: React.CSSProperties = {
  background: "none", border: "none", cursor: "pointer",
  color: "#334155", fontSize: 11, padding: "3px 5px", borderRadius: 4, flexShrink: 0,
};
const PROFILE_SECTION: React.CSSProperties = { flexShrink: 0 };
const DIVIDER: React.CSSProperties = { height: 1, background: "#1e293b", margin: "0 0 10px" };
const PROFILE_ROW: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 8, padding: "2px 4px",
};
const AVATAR: React.CSSProperties = {
  width: 30, height: 30, borderRadius: "50%",
  background: "linear-gradient(135deg, #3b82f6, #6366f1)",
  color: "#fff", fontSize: 13, fontWeight: 700,
  display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
};
const PROFILE_NAME: React.CSSProperties = {
  fontSize: 13, fontWeight: 600, color: "#e2e8f0",
  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
};
const ICON_BTN: React.CSSProperties = {
  background: "none", border: "none", cursor: "pointer",
  color: "#475569", padding: "4px", borderRadius: 6, display: "flex",
  alignItems: "center", justifyContent: "center", flexShrink: 0,
};
const FORM_HEADER: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10,
};
const INPUT: React.CSSProperties = {
  width: "100%", boxSizing: "border-box",
  background: "#1e293b", border: "1px solid #334155",
  borderRadius: 6, color: "#e2e8f0", padding: "6px 9px",
  fontSize: 12, outline: "none",
};
const SELECT: React.CSSProperties = {
  ...({} as React.CSSProperties),
  width: "100%", boxSizing: "border-box",
  background: "#1e293b", border: "1px solid #334155",
  borderRadius: 6, color: "#e2e8f0", padding: "6px 9px",
  fontSize: 12, outline: "none",
};
const SAVE_BTN: React.CSSProperties = {
  marginTop: 12, width: "100%",
  background: "linear-gradient(135deg, #3b82f6, #6366f1)",
  border: "none", borderRadius: 8, color: "#fff",
  padding: "9px 12px", fontSize: 13, fontWeight: 600, cursor: "pointer",
};
