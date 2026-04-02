import { useState, useCallback } from "react";
import LoginForm from "./components/LoginForm";
import Chat from "./components/Chat";
import ConversationList from "./components/ConversationList";

export interface UserProfile {
  author_id: number;
  account_id: string;
  organization_id: number;
  name: string;
  timezone: string;
  team_id: number | null;
}

export interface Conversation {
  session_id: string;
  title: string;
  created_at: string;
}

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const [profile, setProfile]                 = useState<UserProfile | null>(null);
  const [conversations, setConversations]     = useState<Conversation[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [creatingSession, setCreatingSession] = useState(false);

  const createNewSession = useCallback(async (p: UserProfile): Promise<string | null> => {
    setCreatingSession(true);
    try {
      const res = await fetch(`${API_URL}/api/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(p),
      });
      if (!res.ok) throw new Error(await res.text());
      const { session_id } = await res.json();
      return session_id as string;
    } catch (err) {
      console.error("Session creation failed:", err);
      return null;
    } finally {
      setCreatingSession(false);
    }
  }, []);

  const handleLogin = useCallback(async (p: UserProfile) => {
    const sid = await createNewSession(p);
    if (!sid) return;
    setProfile(p);
    setConversations([{ session_id: sid, title: "New Chat", created_at: new Date().toISOString() }]);
    setActiveSessionId(sid);
  }, [createNewSession]);

  const handleNew = useCallback(async () => {
    if (!profile) return;
    const sid = await createNewSession(profile);
    if (!sid) return;
    setConversations(prev => [{ session_id: sid, title: "New Chat", created_at: new Date().toISOString() }, ...prev]);
    setActiveSessionId(sid);
  }, [profile, createNewSession]);

  const handleDelete = useCallback((sid: string) => {
    setConversations(prev => {
      const remaining = prev.filter(c => c.session_id !== sid);
      if (sid === activeSessionId) setActiveSessionId(remaining[0]?.session_id ?? null);
      return remaining;
    });
  }, [activeSessionId]);

  const handleFirstMessage = useCallback((sid: string, text: string) => {
    setConversations(prev =>
      prev.map(c =>
        c.session_id === sid && c.title === "New Chat"
          ? { ...c, title: text.slice(0, 40) + (text.length > 40 ? "…" : "") }
          : c
      )
    );
  }, []);

  const handleLogout = useCallback(() => {
    setProfile(null); setConversations([]); setActiveSessionId(null);
  }, []);

  if (!profile) {
    return <LoginForm onLogin={handleLogin} isLoading={creatingSession} />;
  }

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#f8fafc" }}>
      <ConversationList
        conversations={conversations}
        activeSessionId={activeSessionId}
        userName={profile.name}
        onSelect={setActiveSessionId}
        onDelete={handleDelete}
        onNew={handleNew}
        onLogout={handleLogout}
        isCreating={creatingSession}
      />
      {activeSessionId ? (
        <Chat
          key={activeSessionId}
          sessionId={activeSessionId}
          userProfile={profile}
          onFirstMessage={(text) => handleFirstMessage(activeSessionId, text)}
        />
      ) : (
        <div style={{
          flex: 1, display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", background: "#fff", gap: 12,
        }}>
          <div style={{ fontSize: 48 }}>💬</div>
          <p style={{ color: "#94a3b8", fontSize: 15, fontWeight: 500 }}>
            Select a conversation or start a new chat
          </p>
        </div>
      )}
    </div>
  );
}
