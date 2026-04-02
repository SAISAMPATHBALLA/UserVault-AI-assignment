import React, { useState } from "react";

interface Props {
  original: string;
  reconstructed: string;
  onStop: () => void;
  onEdit: (corrected: string) => void;
}

export default function ReconstructedQuery({ original, reconstructed, onStop, onEdit }: Props) {
  const [editing, setEditing]     = useState(false);
  const [editedText, setEditedText] = useState(reconstructed);

  return (
    <div style={CARD}>
      <div style={{ fontSize: 11, fontWeight: 600, color: "#92400e",
        textTransform: "uppercase", letterSpacing: ".05em", marginBottom: 6 }}>
        Interpreted as
      </div>

      {editing ? (
        <textarea
          value={editedText}
          onChange={e => setEditedText(e.target.value)}
          style={TEXTAREA}
          autoFocus
          rows={3}
        />
      ) : (
        <div style={{ fontStyle: "italic", color: "#1c1917", fontSize: 14,
          marginBottom: 10, lineHeight: 1.5 }}>
          "{reconstructed}"
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
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
            <button style={BTN_GHOST} onClick={() => setEditing(true)}>✏ Edit query</button>
            <button style={BTN_STOP}  onClick={onStop}>✕ Stop</button>
          </>
        )}
      </div>

      {!editing && (
        <div style={{ fontSize: 11, color: "#a8a29e", marginTop: 8 }}>
          Your message: "{original}"
        </div>
      )}
    </div>
  );
}

const CARD: React.CSSProperties = {
  background: "#fffbeb", border: "1.5px solid #fcd34d",
  borderRadius: 10, padding: "12px 16px",
  maxWidth: "76%", margin: "4px 0",
  animation: "fadeIn .2s ease",
};
const BTN: React.CSSProperties = {
  padding: "5px 14px", borderRadius: 6, cursor: "pointer",
  fontSize: 13, fontWeight: 500, border: "none",
};
const BTN_PRIMARY: React.CSSProperties = { ...BTN, background: "#4f46e5", color: "#fff" };
const BTN_GHOST: React.CSSProperties   = { ...BTN, background: "#fff", color: "#374151",
  border: "1px solid #d1d5db" };
const BTN_STOP: React.CSSProperties    = { ...BTN, background: "#fee2e2", color: "#b91c1c",
  border: "1px solid #fca5a5" };
const TEXTAREA: React.CSSProperties = {
  width: "100%", minHeight: 70, fontSize: 13, padding: "8px 10px",
  borderRadius: 6, border: "1px solid #d1d5db", resize: "vertical",
  marginBottom: 8, fontFamily: "inherit", lineHeight: 1.5,
};
