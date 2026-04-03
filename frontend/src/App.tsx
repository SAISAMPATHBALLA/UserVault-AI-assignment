import React, { useState, useCallback } from "react";
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

  // Called when profile is saved or updated from the sidebar form
  const handleProfileUpdate = useCallback(async (p: UserProfile) => {
    const authorChanged = !profile
      || profile.author_id !== p.author_id
      || profile.organization_id !== p.organization_id;

    setProfile(p);

    if (authorChanged) {
      // Different user — create fresh session and clear history
      const sid = await createNewSession(p);
      if (!sid) return;
      setConversations([{ session_id: sid, title: "New Chat", created_at: new Date().toISOString() }]);
      setActiveSessionId(sid);
    }
    // If only name/timezone changed, existing session stays valid
  }, [profile, createNewSession]);

  const handleNew = useCallback(async () => {
    if (!profile) return;
    const sid = await createNewSession(profile);
    if (!sid) return;
    setConversations(prev => [
      { session_id: sid, title: "New Chat", created_at: new Date().toISOString() },
      ...prev,
    ]);
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

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#f1f5f9" }}>
      <ConversationList
        conversations={conversations}
        activeSessionId={activeSessionId}
        profile={profile}
        onSelect={setActiveSessionId}
        onDelete={handleDelete}
        onNew={handleNew}
        onProfileUpdate={handleProfileUpdate}
        isCreating={creatingSession}
      />

      {activeSessionId && profile ? (
        <Chat
          key={activeSessionId}
          sessionId={activeSessionId}
          userProfile={profile}
          onFirstMessage={(text) => handleFirstMessage(activeSessionId, text)}
        />
      ) : (
        <div style={EMPTY_STATE}>
          <div style={EMPTY_ICON}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <p style={{ color: "#64748b", fontSize: 15, fontWeight: 600, margin: "0 0 6px" }}>
            {profile ? "Select or start a conversation" : "Set up your profile to begin"}
          </p>
          <p style={{ color: "#94a3b8", fontSize: 13, margin: 0 }}>
            {profile
              ? "Choose a chat from the sidebar or create a new one"
              : "Fill in your profile details in the sidebar"}
          </p>
        </div>
      )}
    </div>
  );
}

const EMPTY_STATE: React.CSSProperties = {
  flex: 1,
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  background: "#f8fafc",
  gap: 8,
};
const EMPTY_ICON: React.CSSProperties = {
  width: 80,
  height: 80,
  borderRadius: "50%",
  background: "#f1f5f9",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  marginBottom: 12,
};
