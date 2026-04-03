import React, { useState } from "react";

interface Props {
  original: string;
  reconstructed: string;
  onStop: () => void;
  onEdit: (corrected: string) => void;
}

export default function ReconstructedQuery({ original, reconstructed, onStop, onEdit }: Props) {
  const [editing, setEditing]       = useState(false);
  const [editedText, setEditedText] = useState(reconstructed);

  return (
    <div style={WRAPPER}>
      <div style={LABEL}>
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ marginRight: 4 }}>
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        Interpreted as
      </div>

      {editing ? (
        <textarea
          value={editedText}
          onChange={e => setEditedText(e.target.value)}
          autoFocus
          rows={2}
          style={EDIT_INPUT}
        />
      ) : (
        <div style={QUERY_TEXT}>"{reconstructed}"</div>
      )}

      <div style={HINT}>Your message: "{original}"</div>

      <div style={ACTIONS}>
        {editing ? (
          <>
            <button style={BTN_PRIMARY} onClick={() => { onEdit(editedText); setEditing(false); }}>
              Submit
            </button>
            <button style={BTN_GHOST} onClick={() => { setEditing(false); setEditedText(reconstructed); }}>
              Cancel
            </button>
          </>
        ) : (
          <>
            <button style={BTN_GHOST} onClick={() => setEditing(true)}>
              ✏ Edit
            </button>
            <button style={BTN_STOP} onClick={onStop}>
              ✕ Stop
            </button>
          </>
        )}
      </div>
    </div>
  );
}

const WRAPPER: React.CSSProperties = {
  background: "#fff",
  border: "1px solid #e2e8f0",
  borderLeft: "3px solid #f59e0b",
  borderRadius: 10,
  padding: "12px 14px",
  maxWidth: "75%",
  display: "flex", flexDirection: "column", gap: 6,
  boxShadow: "0 1px 4px rgba(0,0,0,.05)",
};
const LABEL: React.CSSProperties = {
  fontSize: 10, fontWeight: 700, color: "#92400e",
  textTransform: "uppercase", letterSpacing: ".06em",
  display: "flex", alignItems: "center",
};
const QUERY_TEXT: React.CSSProperties = {
  fontStyle: "italic", color: "#1e293b", fontSize: 13, lineHeight: 1.55,
};
const HINT: React.CSSProperties = {
  fontSize: 11, color: "#94a3b8",
};
const EDIT_INPUT: React.CSSProperties = {
  width: "100%", boxSizing: "border-box",
  border: "1px solid #e2e8f0", borderRadius: 6,
  padding: "7px 10px", fontSize: 13, outline: "none",
  fontFamily: "inherit", resize: "none",
};
const ACTIONS: React.CSSProperties = { display: "flex", gap: 6, marginTop: 2 };
const BTN_BASE: React.CSSProperties = {
  border: "1px solid #e2e8f0", borderRadius: 6,
  padding: "4px 10px", fontSize: 12, cursor: "pointer", fontWeight: 500,
};
const BTN_PRIMARY: React.CSSProperties = {
  ...BTN_BASE, background: "#4f46e5", color: "#fff", border: "none",
};
const BTN_GHOST: React.CSSProperties = {
  ...BTN_BASE, background: "#fff", color: "#475569",
};
const BTN_STOP: React.CSSProperties = {
  ...BTN_BASE, background: "#fff", color: "#ef4444", borderColor: "#fecaca",
};
