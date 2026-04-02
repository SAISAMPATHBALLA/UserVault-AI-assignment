import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
const TIMEZONES = [
    "UTC", "Asia/Kolkata", "Asia/Singapore", "Asia/Tokyo",
    "America/New_York", "America/Los_Angeles", "America/Chicago",
    "Europe/London", "Europe/Berlin", "Europe/Paris",
    "Australia/Sydney",
];
export default function LoginForm({ onLogin, isLoading }) {
    const [form, setForm] = useState({
        name: "",
        author_id: "",
        account_id: "",
        organization_id: "",
        team_id: "",
        timezone: "Asia/Kolkata",
    });
    const [error, setError] = useState("");
    const set = (k) => (e) => setForm(prev => ({ ...prev, [k]: e.target.value }));
    const handleSubmit = (e) => {
        e.preventDefault();
        setError("");
        if (!form.name.trim() || !form.author_id || !form.account_id || !form.organization_id) {
            setError("Please fill in all required fields.");
            return;
        }
        const author_id = Number(form.author_id);
        const organization_id = Number(form.organization_id);
        const team_id = form.team_id ? Number(form.team_id) : null;
        if (!Number.isInteger(author_id) || author_id <= 0) {
            setError("Author ID must be a positive integer.");
            return;
        }
        if (!Number.isInteger(organization_id) || organization_id <= 0) {
            setError("Organization ID must be a positive integer.");
            return;
        }
        onLogin({ name: form.name.trim(), author_id, account_id: form.account_id.trim(), organization_id, team_id, timezone: form.timezone });
    };
    return (_jsx("div", { style: OUTER, children: _jsxs("div", { style: CARD, children: [_jsxs("div", { style: { textAlign: "center", marginBottom: 28 }, children: [_jsx("div", { style: { fontSize: 36, marginBottom: 8 }, children: "\uD83D\uDCCA" }), _jsx("h1", { style: { fontSize: 22, fontWeight: 700, color: "#111" }, children: "Developer Analytics" }), _jsx("p", { style: { color: "#6b7280", fontSize: 14, marginTop: 4 }, children: "Ask questions about your commits, pull requests, and performance" })] }), _jsxs("form", { onSubmit: handleSubmit, style: { display: "flex", flexDirection: "column", gap: 14 }, children: [_jsx(Field, { label: "Display Name *", type: "text", placeholder: "e.g. Alex Kumar", value: form.name, onChange: set("name") }), _jsx(Field, { label: "Author ID *", type: "number", placeholder: "e.g. 12345", value: form.author_id, onChange: set("author_id") }), _jsx(Field, { label: "Account ID *", type: "text", placeholder: "e.g. acc_abc123", value: form.account_id, onChange: set("account_id") }), _jsx(Field, { label: "Organization ID *", type: "number", placeholder: "e.g. 67890", value: form.organization_id, onChange: set("organization_id") }), _jsx(Field, { label: "Team ID", type: "number", placeholder: "Optional", value: form.team_id, onChange: set("team_id") }), _jsxs("div", { style: { display: "flex", flexDirection: "column", gap: 5 }, children: [_jsx("label", { style: LABEL_STYLE, children: "Timezone" }), _jsx("select", { value: form.timezone, onChange: set("timezone"), style: SELECT_STYLE, children: TIMEZONES.map(tz => _jsx("option", { value: tz, children: tz }, tz)) })] }), error && (_jsx("div", { style: { background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 6,
                                padding: "8px 12px", fontSize: 13, color: "#dc2626" }, children: error })), _jsx("button", { type: "submit", disabled: isLoading, style: { ...SUBMIT_BTN, opacity: isLoading ? 0.7 : 1 }, children: isLoading ? "Connecting…" : "Start Chatting →" })] })] }) }));
}
function Field({ label, type, placeholder, value, onChange }) {
    return (_jsxs("div", { style: { display: "flex", flexDirection: "column", gap: 5 }, children: [_jsx("label", { style: LABEL_STYLE, children: label }), _jsx("input", { type: type, placeholder: placeholder, value: value, onChange: onChange, style: INPUT_STYLE, required: label.includes("*") })] }));
}
const OUTER = {
    minHeight: "100vh", display: "flex", alignItems: "center",
    justifyContent: "center", background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
};
const CARD = {
    background: "#fff", borderRadius: 16, padding: "36px 40px",
    width: "100%", maxWidth: 440, boxShadow: "0 20px 60px rgba(0,0,0,.15)",
};
const LABEL_STYLE = {
    fontSize: 13, fontWeight: 600, color: "#374151",
};
const INPUT_STYLE = {
    padding: "9px 12px", borderRadius: 8, border: "1.5px solid #d1d5db",
    fontSize: 14, outline: "none", width: "100%",
    transition: "border-color .15s",
};
const SELECT_STYLE = {
    ...INPUT_STYLE, background: "#fff", cursor: "pointer",
};
const SUBMIT_BTN = {
    padding: "11px", background: "#4f46e5", color: "#fff",
    border: "none", borderRadius: 8, fontSize: 15, fontWeight: 600,
    cursor: "pointer", marginTop: 4, width: "100%",
    transition: "opacity .15s",
};
