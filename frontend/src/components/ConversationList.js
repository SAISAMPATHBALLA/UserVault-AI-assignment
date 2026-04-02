import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
function timeAgo(iso) {
    const diff = Date.now() - new Date(iso).getTime();
    const m = Math.floor(diff / 60000);
    if (m < 1)
        return "just now";
    if (m < 60)
        return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24)
        return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
}
export default function ConversationList({ conversations, activeSessionId, userName, onSelect, onDelete, onNew, onLogout, isCreating, }) {
    return (_jsxs("div", { style: SIDEBAR, children: [_jsxs("div", { style: BRAND, children: [_jsx("span", { style: { fontSize: 18 }, children: "\uD83D\uDCCA" }), _jsx("span", { style: { fontWeight: 700, fontSize: 14, color: "#fff" }, children: "Dev Analytics" })] }), _jsx("button", { style: { ...NEW_BTN, opacity: isCreating ? 0.7 : 1 }, onClick: onNew, disabled: isCreating, children: isCreating ? "Creating…" : "+ New Chat" }), _jsxs("div", { style: { flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 2 }, children: [_jsx("div", { style: { fontSize: 10, fontWeight: 600, color: "#6b7280", padding: "8px 10px 4px",
                            textTransform: "uppercase", letterSpacing: ".06em" }, children: "Recent" }), conversations.map(c => (_jsxs("div", { style: {
                            ...ITEM, background: c.session_id === activeSessionId ? "#1e2a3a" : "transparent",
                        }, children: [_jsxs("div", { style: { flex: 1, cursor: "pointer", overflow: "hidden" }, onClick: () => onSelect(c.session_id), children: [_jsx("div", { style: { fontSize: 13, fontWeight: 500, color: "#e2e8f0",
                                            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }, children: c.title }), _jsx("div", { style: { fontSize: 11, color: "#6b7280", marginTop: 2 }, children: timeAgo(c.created_at) })] }), _jsx("button", { title: "Delete", style: DEL_BTN, onClick: e => { e.stopPropagation(); onDelete(c.session_id); }, children: "\u2715" })] }, c.session_id))), conversations.length === 0 && (_jsx("div", { style: { color: "#4b5563", fontSize: 13, padding: "12px 10px" }, children: "No conversations yet" }))] }), _jsxs("div", { style: FOOTER, children: [_jsxs("div", { style: { overflow: "hidden" }, children: [_jsx("div", { style: { fontSize: 13, fontWeight: 600, color: "#e2e8f0",
                                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }, children: userName }), _jsx("div", { style: { fontSize: 11, color: "#6b7280" }, children: "Signed in" })] }), _jsx("button", { style: LOGOUT_BTN, onClick: onLogout, title: "Sign out", children: "\u21E0" })] })] }));
}
const SIDEBAR = {
    width: 240, background: "#111827",
    display: "flex", flexDirection: "column",
    padding: "12px 10px", gap: 8,
    height: "100vh", flexShrink: 0,
};
const BRAND = {
    display: "flex", alignItems: "center", gap: 8,
    padding: "4px 6px 10px", borderBottom: "1px solid #1f2937",
};
const NEW_BTN = {
    padding: "9px 12px", background: "#4f46e5", color: "#fff",
    border: "none", borderRadius: 8, cursor: "pointer",
    fontWeight: 600, fontSize: 13, textAlign: "left",
    transition: "opacity .15s",
};
const ITEM = {
    display: "flex", alignItems: "center", padding: "8px 8px",
    borderRadius: 7, gap: 6, transition: "background .1s",
};
const DEL_BTN = {
    background: "none", border: "none", cursor: "pointer",
    color: "#4b5563", fontSize: 12, padding: "2px 5px",
    borderRadius: 4, flexShrink: 0,
    transition: "color .1s",
};
const FOOTER = {
    display: "flex", alignItems: "center", gap: 8,
    padding: "10px 6px 4px", borderTop: "1px solid #1f2937",
};
const LOGOUT_BTN = {
    background: "none", border: "1px solid #374151", cursor: "pointer",
    color: "#6b7280", fontSize: 14, padding: "4px 8px",
    borderRadius: 6, flexShrink: 0,
};
