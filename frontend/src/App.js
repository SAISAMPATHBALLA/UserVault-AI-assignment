import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useCallback } from "react";
import LoginForm from "./components/LoginForm";
import Chat from "./components/Chat";
import ConversationList from "./components/ConversationList";
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
export default function App() {
    const [profile, setProfile] = useState(null);
    const [conversations, setConversations] = useState([]);
    const [activeSessionId, setActiveSessionId] = useState(null);
    const [creatingSession, setCreatingSession] = useState(false);
    const createNewSession = useCallback(async (p) => {
        setCreatingSession(true);
        try {
            const res = await fetch(`${API_URL}/api/session`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(p),
            });
            if (!res.ok)
                throw new Error(await res.text());
            const { session_id } = await res.json();
            return session_id;
        }
        catch (err) {
            console.error("Session creation failed:", err);
            return null;
        }
        finally {
            setCreatingSession(false);
        }
    }, []);
    const handleLogin = useCallback(async (p) => {
        const sid = await createNewSession(p);
        if (!sid)
            return;
        setProfile(p);
        setConversations([{ session_id: sid, title: "New Chat", created_at: new Date().toISOString() }]);
        setActiveSessionId(sid);
    }, [createNewSession]);
    const handleNew = useCallback(async () => {
        if (!profile)
            return;
        const sid = await createNewSession(profile);
        if (!sid)
            return;
        setConversations(prev => [{ session_id: sid, title: "New Chat", created_at: new Date().toISOString() }, ...prev]);
        setActiveSessionId(sid);
    }, [profile, createNewSession]);
    const handleDelete = useCallback((sid) => {
        setConversations(prev => {
            const remaining = prev.filter(c => c.session_id !== sid);
            if (sid === activeSessionId)
                setActiveSessionId(remaining[0]?.session_id ?? null);
            return remaining;
        });
    }, [activeSessionId]);
    const handleFirstMessage = useCallback((sid, text) => {
        setConversations(prev => prev.map(c => c.session_id === sid && c.title === "New Chat"
            ? { ...c, title: text.slice(0, 40) + (text.length > 40 ? "…" : "") }
            : c));
    }, []);
    const handleLogout = useCallback(() => {
        setProfile(null);
        setConversations([]);
        setActiveSessionId(null);
    }, []);
    if (!profile) {
        return _jsx(LoginForm, { onLogin: handleLogin, isLoading: creatingSession });
    }
    return (_jsxs("div", { style: { display: "flex", height: "100vh", overflow: "hidden" }, children: [_jsx(ConversationList, { conversations: conversations, activeSessionId: activeSessionId, userName: profile.name, onSelect: setActiveSessionId, onDelete: handleDelete, onNew: handleNew, onLogout: handleLogout, isCreating: creatingSession }), activeSessionId ? (_jsx(Chat, { sessionId: activeSessionId, userProfile: profile, onFirstMessage: (text) => handleFirstMessage(activeSessionId, text) }, activeSessionId)) : (_jsxs("div", { style: { flex: 1, display: "flex", flexDirection: "column",
                    alignItems: "center", justifyContent: "center", background: "#fff", gap: 12 }, children: [_jsx("span", { style: { fontSize: 40 }, children: "\uD83D\uDCAC" }), _jsx("p", { style: { color: "#6b7280", fontSize: 15 }, children: "Select a conversation or start a new chat" })] }))] }));
}
