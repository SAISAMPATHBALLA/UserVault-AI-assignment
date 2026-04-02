import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/// <reference types="vite/client" />
import { useEffect, useRef, useState, useCallback } from "react";
import Message from "./Message";
import ReconstructedQuery from "./ReconstructedQuery";
const WS_BASE = import.meta.env.VITE_WS_URL || "ws://localhost:8000";
export default function Chat({ sessionId, userProfile, onFirstMessage }) {
    const [msgs, setMsgs] = useState([]);
    const [input, setInput] = useState("");
    const [connected, setConnected] = useState(false);
    const [status, setStatus] = useState(null);
    const wsRef = useRef(null);
    const bottomRef = useRef(null);
    const firstMsgSent = useRef(false);
    const inputRef = useRef(null);
    // WebSocket connection
    useEffect(() => {
        const ws = new WebSocket(`${WS_BASE}/ws/chat/${sessionId}`);
        wsRef.current = ws;
        setMsgs([]);
        firstMsgSent.current = false;
        ws.onopen = () => { setConnected(true); inputRef.current?.focus(); };
        ws.onclose = () => { setConnected(false); setStatus(null); };
        ws.onerror = () => setStatus("Connection error — reconnecting…");
        ws.onmessage = (ev) => {
            const msg = JSON.parse(ev.data);
            switch (msg.type) {
                case "status":
                    setStatus(msg.message);
                    break;
                case "reconstructed_query":
                    setStatus(null);
                    addMsg({ kind: "reconstructed", original: msg.original, reconstructed: msg.query });
                    break;
                case "token":
                    setStatus(null);
                    setMsgs(prev => {
                        const last = prev[prev.length - 1];
                        if (last?.role === "assistant" && last.isStreaming) {
                            return [...prev.slice(0, -1), { ...last, content: (last.content ?? "") + msg.content }];
                        }
                        return [...prev, newMsg("assistant", msg.content, true)];
                    });
                    break;
                case "done":
                    setStatus(null);
                    setMsgs(prev => {
                        const last = prev[prev.length - 1];
                        return last?.isStreaming ? [...prev.slice(0, -1), { ...last, isStreaming: false }] : prev;
                    });
                    break;
                case "rejected":
                    setStatus(null);
                    addMsg({ kind: "message", role: "rejected", content: msg.reason });
                    break;
                case "followup":
                    setStatus(null);
                    addMsg({ kind: "message", role: "followup", content: msg.message });
                    break;
                case "error":
                    setStatus(null);
                    addMsg({ kind: "message", role: "error", content: msg.message });
                    break;
            }
        };
        return () => ws.close();
    }, [sessionId]);
    // Auto-scroll
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [msgs, status]);
    const addMsg = (partial) => {
        setMsgs(prev => [...prev, { id: crypto.randomUUID(), kind: "message", ...partial }]);
    };
    const newMsg = (role, content, isStreaming = false) => ({
        id: crypto.randomUUID(), kind: "message", role, content, isStreaming,
    });
    const wsSend = useCallback((obj) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(obj));
        }
    }, []);
    const submitQuestion = (text) => {
        const trimmed = text.trim();
        if (!trimmed || status || !connected)
            return;
        if (!firstMsgSent.current) {
            firstMsgSent.current = true;
            onFirstMessage(trimmed);
        }
        addMsg({ kind: "message", role: "user", content: trimmed });
        setInput("");
        setStatus("Understanding your question…");
        wsSend({ type: "question", text: trimmed, user_profile: userProfile });
    };
    const handleStop = () => {
        wsSend({ type: "stop" });
        setStatus(null);
        setMsgs(prev => prev.filter(m => m.kind !== "reconstructed"));
    };
    const handleEdit = (corrected) => {
        setMsgs(prev => prev.filter(m => m.kind !== "reconstructed"));
        addMsg({ kind: "message", role: "user", content: `↩ Edited: ${corrected}` });
        setStatus("Processing edited query…");
        wsSend({ type: "edit", query: corrected, user_profile: userProfile });
    };
    const handleKeyDown = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submitQuestion(input);
        }
    };
    const isIdle = connected && !status;
    return (_jsxs("div", { style: CONTAINER, children: [_jsxs("div", { style: HEADER, children: [_jsx("span", { style: { fontWeight: 600, fontSize: 15, color: "#111" }, children: "Developer Analytics" }), _jsx("span", { style: { fontSize: 12, color: connected ? "#16a34a" : "#dc2626", fontWeight: 500 }, children: connected ? "● Live" : "○ Offline" })] }), _jsxs("div", { style: MESSAGES_AREA, children: [msgs.length === 0 && !status && (_jsxs("div", { style: EMPTY_HINT, children: [_jsx("p", { style: { fontSize: 24, marginBottom: 8 }, children: "\uD83D\uDC4B" }), _jsx("p", { style: { color: "#6b7280", fontSize: 14 }, children: "Ask me about your commits, pull requests, code reviews, or performance scores." })] })), msgs.map(m => m.kind === "reconstructed" ? (_jsx(ReconstructedQuery, { original: m.original, reconstructed: m.reconstructed, onStop: handleStop, onEdit: handleEdit }, m.id)) : (_jsx(Message, { role: m.role, content: m.content, isStreaming: m.isStreaming }, m.id))), status && (_jsxs("div", { style: STATUS_ROW, children: [_jsx(Spinner, {}), _jsx("span", { style: { fontSize: 13, color: "#6b7280" }, children: status })] })), _jsx("div", { ref: bottomRef })] }), _jsxs("div", { style: INPUT_AREA, children: [_jsx("textarea", { ref: inputRef, value: input, onChange: e => setInput(e.target.value), onKeyDown: handleKeyDown, placeholder: isIdle ? "Ask about your data… (Enter to send, Shift+Enter for new line)" : status ? "Processing…" : "Connecting…", disabled: !isIdle, rows: 2, style: { ...TEXTAREA, background: isIdle ? "#fff" : "#f9fafb" } }), _jsx("button", { onClick: () => submitQuestion(input), disabled: !isIdle || !input.trim(), style: { ...SEND_BTN, opacity: (!isIdle || !input.trim()) ? 0.5 : 1 }, children: "Send" })] })] }));
}
function Spinner() {
    return (_jsx("div", { style: {
            width: 14, height: 14, borderRadius: "50%",
            border: "2px solid #e5e7eb", borderTopColor: "#6366f1",
            animation: "spin .7s linear infinite", flexShrink: 0,
        } }));
}
// ── Styles ────────────────────────────────────────────────────────────────────
const CONTAINER = {
    flex: 1, display: "flex", flexDirection: "column",
    height: "100vh", background: "#fff", overflow: "hidden",
};
const HEADER = {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    padding: "12px 20px", borderBottom: "1px solid #e5e7eb",
    background: "#fff", flexShrink: 0,
};
const MESSAGES_AREA = {
    flex: 1, overflowY: "auto", padding: "20px",
    display: "flex", flexDirection: "column", gap: 8,
};
const STATUS_ROW = {
    display: "flex", alignItems: "center", gap: 8,
    padding: "4px 0", marginTop: 4,
};
const INPUT_AREA = {
    display: "flex", gap: 10, padding: "12px 16px",
    borderTop: "1px solid #e5e7eb", background: "#fff", flexShrink: 0,
    alignItems: "flex-end",
};
const TEXTAREA = {
    flex: 1, padding: "10px 14px", borderRadius: 10,
    border: "1.5px solid #d1d5db", fontSize: 14, resize: "none",
    outline: "none", lineHeight: 1.5, fontFamily: "inherit",
};
const SEND_BTN = {
    padding: "10px 20px", background: "#4f46e5", color: "#fff",
    border: "none", borderRadius: 10, cursor: "pointer",
    fontWeight: 600, fontSize: 14, flexShrink: 0,
    transition: "opacity .15s",
};
const EMPTY_HINT = {
    flex: 1, display: "flex", flexDirection: "column",
    alignItems: "center", justifyContent: "center", textAlign: "center",
    padding: "0 40px", gap: 4,
};
