import React, { useState } from "react";
import Chat from "./components/Chat";
import ConversationList from "./components/ConversationList";

// In production this would come from auth/login
const DEMO_USER_PROFILE = {
  name: "Sam",
  id: 1,
  email: "sam@example.com",
  city: "Mumbai",
};

interface Conversation {
  session_id: string;
  title?: string;
  created_at: string;
}

const generateSessionId = () => crypto.randomUUID();

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>([
    { session_id: generateSessionId(), title: "New Chat", created_at: new Date().toISOString() }
  ]);
  const [activeSessionId, setActiveSessionId] = useState(conversations[0].session_id);

  const handleNew = () => {
    const newConv: Conversation = {
      session_id: generateSessionId(),
      title: "New Chat",
      created_at: new Date().toISOString(),
    };
    setConversations(prev => [newConv, ...prev]);
    setActiveSessionId(newConv.session_id);
  };

  const handleDelete = (sessionId: string) => {
    setConversations(prev => prev.filter(c => c.session_id !== sessionId));
    if (sessionId === activeSessionId) {
      const remaining = conversations.filter(c => c.session_id !== sessionId);
      if (remaining.length > 0) setActiveSessionId(remaining[0].session_id);
      else handleNew();
    }
  };

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "system-ui, sans-serif" }}>
      <ConversationList
        conversations={conversations}
        activeSessionId={activeSessionId}
        onSelect={setActiveSessionId}
        onDelete={handleDelete}
        onNew={handleNew}
      />
      <Chat
        key={activeSessionId}
        sessionId={activeSessionId}
        userProfile={DEMO_USER_PROFILE}
      />
    </div>
  );
}
