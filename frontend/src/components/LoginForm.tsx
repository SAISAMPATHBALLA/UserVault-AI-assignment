import React, { useState } from "react";
import {
  Form,
  Button,
  SelectPicker,
  Panel,
  Stack,
  Input,
  InputGroup,
  Message,
  Loader,
} from "rsuite";
import type { UserProfile } from "../App";

const TIMEZONES = [
  "UTC", "Asia/Kolkata", "Asia/Singapore", "Asia/Tokyo",
  "America/New_York", "America/Los_Angeles", "America/Chicago",
  "Europe/London", "Europe/Berlin", "Europe/Paris",
  "Australia/Sydney",
].map(tz => ({ label: tz, value: tz }));

interface Props {
  onLogin: (profile: UserProfile) => void;
  isLoading: boolean;
}

export default function LoginForm({ onLogin, isLoading }: Props) {
  const [form, setForm] = useState({
    name: "",
    author_id: "",
    account_id: "",
    organization_id: "",
    team_id: "",
    timezone: "Asia/Kolkata",
  });
  const [error, setError] = useState("");

  const set = (k: keyof typeof form) => (val: string) =>
    setForm(prev => ({ ...prev, [k]: val }));

  const handleSubmit = () => {
    setError("");
    if (!form.name.trim() || !form.author_id || !form.account_id || !form.organization_id) {
      setError("Please fill in all required fields.");
      return;
    }
    const author_id = Number(form.author_id);
    const organization_id = Number(form.organization_id);
    const team_id = form.team_id ? Number(form.team_id) : null;
    if (!Number.isInteger(author_id) || author_id <= 0) {
      setError("Author ID must be a positive integer."); return;
    }
    if (!Number.isInteger(organization_id) || organization_id <= 0) {
      setError("Organization ID must be a positive integer."); return;
    }
    onLogin({ name: form.name.trim(), author_id, account_id: form.account_id.trim(), organization_id, team_id, timezone: form.timezone });
  };

  return (
    <div style={OUTER}>
      <Panel
        style={CARD}
        header={
          <div style={{ textAlign: "center", padding: "8px 0 4px" }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>📊</div>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: "#0f172a", margin: 0 }}>
              Developer Analytics
            </h2>
            <p style={{ color: "#64748b", fontSize: 13, marginTop: 6 }}>
              Ask questions about your commits, pull requests, and performance
            </p>
          </div>
        }
        bordered
      >
        <Form fluid style={{ marginTop: 8 }}>
          <Stack direction="column" spacing={14} alignItems="stretch">

            <Form.Group>
              <Form.ControlLabel>Display Name <span style={{ color: "#ef4444" }}>*</span></Form.ControlLabel>
              <Input placeholder="e.g. Alex Kumar" value={form.name} onChange={set("name")} />
            </Form.Group>

            <Form.Group>
              <Form.ControlLabel>Author ID <span style={{ color: "#ef4444" }}>*</span></Form.ControlLabel>
              <Input type="number" placeholder="e.g. 12345" value={form.author_id} onChange={set("author_id")} />
            </Form.Group>

            <Form.Group>
              <Form.ControlLabel>Account ID <span style={{ color: "#ef4444" }}>*</span></Form.ControlLabel>
              <Input placeholder="e.g. acc_abc123" value={form.account_id} onChange={set("account_id")} />
            </Form.Group>

            <Form.Group>
              <Form.ControlLabel>Organization ID <span style={{ color: "#ef4444" }}>*</span></Form.ControlLabel>
              <Input type="number" placeholder="e.g. 67890" value={form.organization_id} onChange={set("organization_id")} />
            </Form.Group>

            <Form.Group>
              <Form.ControlLabel>Team ID <span style={{ color: "#94a3b8", fontSize: 11 }}>(optional)</span></Form.ControlLabel>
              <Input type="number" placeholder="Optional" value={form.team_id} onChange={set("team_id")} />
            </Form.Group>

            <Form.Group>
              <Form.ControlLabel>Timezone</Form.ControlLabel>
              <SelectPicker
                data={TIMEZONES}
                value={form.timezone}
                onChange={val => set("timezone")(val ?? "UTC")}
                cleanable={false}
                block
                searchable
              />
            </Form.Group>

            {error && (
              <Message type="error" showIcon>
                {error}
              </Message>
            )}

            <Button
              appearance="primary"
              block
              onClick={handleSubmit}
              disabled={isLoading}
              style={{ marginTop: 4, fontWeight: 600, fontSize: 15, padding: "11px" }}
            >
              {isLoading ? <><Loader size="xs" style={{ marginRight: 6 }} />Connecting…</> : "Start Chatting →"}
            </Button>

          </Stack>
        </Form>
      </Panel>
    </div>
  );
}

const OUTER: React.CSSProperties = {
  minHeight: "100vh",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
  padding: "24px",
};
const CARD: React.CSSProperties = {
  background: "#fff",
  borderRadius: 16,
  width: "100%",
  maxWidth: 440,
  boxShadow: "0 24px 64px rgba(0,0,0,.18)",
  padding: "8px 8px",
};
