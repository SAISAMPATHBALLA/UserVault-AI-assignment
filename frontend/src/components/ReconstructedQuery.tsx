import React, { useState } from "react";
import { Panel, Button, Input } from "rsuite";

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
    <Panel
      style={{
        background: "#fffbeb",
        border: "1.5px solid #fbbf24",
        borderRadius: 12,
        padding: "12px 16px",
        maxWidth: "76%",
        animation: "fadeIn .2s ease",
      }}
    >
      <div style={{
        fontSize: 11, fontWeight: 700, color: "#92400e",
        textTransform: "uppercase", letterSpacing: ".05em", marginBottom: 8,
      }}>
        Interpreted as
      </div>

      {editing ? (
        <Input
          as="textarea"
          value={editedText}
          onChange={(val: string) => setEditedText(val)}
          autoFocus
          rows={3}
          style={{ marginBottom: 10, fontSize: 13 }}
        />
      ) : (
        <div style={{
          fontStyle: "italic", color: "#1c1917", fontSize: 14,
          marginBottom: 10, lineHeight: 1.55,
        }}>
          "{reconstructed}"
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
        {editing ? (
          <>
            <Button
              appearance="primary"
              size="sm"
              onClick={() => { onEdit(editedText); setEditing(false); }}
            >
              Submit
            </Button>
            <Button
              appearance="subtle"
              size="sm"
              onClick={() => { setEditing(false); setEditedText(reconstructed); }}
            >
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button appearance="ghost" size="sm" onClick={() => setEditing(true)}>
              ✏ Edit query
            </Button>
            <Button appearance="subtle" size="sm" color="red" onClick={onStop}>
              ✕ Stop
            </Button>
          </>
        )}
      </div>

      {!editing && (
        <div style={{ fontSize: 11, color: "#a8a29e", marginTop: 8 }}>
          Your message: "{original}"
        </div>
      )}
    </Panel>
  );
}
