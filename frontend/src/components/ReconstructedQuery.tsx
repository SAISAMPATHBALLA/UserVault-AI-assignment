import React, { useState } from "react";

interface Props {
  original: string;
  reconstructed: string;
  onStop: () => void;
  onEdit: (corrected: string) => void;
}

const ReconstructedQuery: React.FC<Props> = ({ original, reconstructed, onStop, onEdit }) => {
  const [editing, setEditing] = useState(false);
  const [editedText, setEditedText] = useState(reconstructed);

  return (
    <div style={CARD}>
      <div style={{ fontSize: 11, color: "#888", marginBottom: 4 }}>
        Interpreted your question as:
      </div>

      {editing ? (
        <textarea
          value={editedText}
          onChange={e => setEditedText(e.target.value)}
          style={TEXTAREA}
          autoFocus
        />
      ) : (
        <div style={{ fontStyle: "italic", color: "#333", fontSize: 14, marginBottom: 8 }}>
          "{reconstructed}"
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
        {editing ? (
          <>
            <button style={BTN_PRIMARY} onClick={() => { onEdit(editedText); setEditing(false); }}>
              Submit edited query
            </button>
            <button style={BTN_GHOST} onClick={() => setEditing(false)}>Cancel</button>
          </>
        ) : (
          <>
            <button style={BTN_WARN} onClick={onStop}>Stop</button>
            <button style={BTN_GHOST} onClick={() => setEditing(true)}>Edit Query</button>
          </>
        )}
      </div>

      {!editing && (
        <div style={{ fontSize: 11, color: "#aaa", marginTop: 6 }}>
          Original: "{original}"
        </div>
      )}
    </div>
  );
};

const CARD: React.CSSProperties = {
  background: "#fffbea",
  border: "1px solid #f0c040",
  borderRadius: 8,
  padding: "12px 16px",
  maxWidth: "78%",
  margin: "4px 0",
};
const BTN: React.CSSProperties = {
  padding: "5px 14px", borderRadius: 5, cursor: "pointer", fontSize: 13, border: "none",
};
const BTN_WARN: React.CSSProperties    = { ...BTN, background: "#ff5252", color: "#fff" };
const BTN_PRIMARY: React.CSSProperties = { ...BTN, background: "#2196F3", color: "#fff" };
const BTN_GHOST: React.CSSProperties   = { ...BTN, background: "#eee", color: "#333", border: "1px solid #ccc" };
const TEXTAREA: React.CSSProperties = {
  width: "100%", minHeight: 60, fontSize: 13, padding: 6, borderRadius: 4,
  border: "1px solid #ccc", resize: "vertical",
};

export default ReconstructedQuery;
