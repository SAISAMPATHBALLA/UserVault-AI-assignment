import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from "react";
export default function ReconstructedQuery({ original, reconstructed, onStop, onEdit }) {
    const [editing, setEditing] = useState(false);
    const [editedText, setEditedText] = useState(reconstructed);
    return (_jsxs("div", { style: CARD, children: [_jsx("div", { style: { fontSize: 11, fontWeight: 600, color: "#92400e",
                    textTransform: "uppercase", letterSpacing: ".05em", marginBottom: 6 }, children: "Interpreted as" }), editing ? (_jsx("textarea", { value: editedText, onChange: e => setEditedText(e.target.value), style: TEXTAREA, autoFocus: true, rows: 3 })) : (_jsxs("div", { style: { fontStyle: "italic", color: "#1c1917", fontSize: 14,
                    marginBottom: 10, lineHeight: 1.5 }, children: ["\"", reconstructed, "\""] })), _jsx("div", { style: { display: "flex", gap: 8, marginTop: 4 }, children: editing ? (_jsxs(_Fragment, { children: [_jsx("button", { style: BTN_PRIMARY, onClick: () => { onEdit(editedText); setEditing(false); }, children: "Submit" }), _jsx("button", { style: BTN_GHOST, onClick: () => { setEditing(false); setEditedText(reconstructed); }, children: "Cancel" })] })) : (_jsxs(_Fragment, { children: [_jsx("button", { style: BTN_GHOST, onClick: () => setEditing(true), children: "\u270F Edit query" }), _jsx("button", { style: BTN_STOP, onClick: onStop, children: "\u2715 Stop" })] })) }), !editing && (_jsxs("div", { style: { fontSize: 11, color: "#a8a29e", marginTop: 8 }, children: ["Your message: \"", original, "\""] }))] }));
}
const CARD = {
    background: "#fffbeb", border: "1.5px solid #fcd34d",
    borderRadius: 10, padding: "12px 16px",
    maxWidth: "76%", margin: "4px 0",
    animation: "fadeIn .2s ease",
};
const BTN = {
    padding: "5px 14px", borderRadius: 6, cursor: "pointer",
    fontSize: 13, fontWeight: 500, border: "none",
};
const BTN_PRIMARY = { ...BTN, background: "#4f46e5", color: "#fff" };
const BTN_GHOST = { ...BTN, background: "#fff", color: "#374151",
    border: "1px solid #d1d5db" };
const BTN_STOP = { ...BTN, background: "#fee2e2", color: "#b91c1c",
    border: "1px solid #fca5a5" };
const TEXTAREA = {
    width: "100%", minHeight: 70, fontSize: 13, padding: "8px 10px",
    borderRadius: 6, border: "1px solid #d1d5db", resize: "vertical",
    marginBottom: 8, fontFamily: "inherit", lineHeight: 1.5,
};
