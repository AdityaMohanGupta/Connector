import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { AuditLog, CalendarEvent, ChatMessage, Folder, Message, PendingAction, User } from "./types";

const formatDate = (value?: string | null) => {
  if (!value) return "No date";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
};

const inputDateTime = (value?: string) => {
  if (!value) return "";
  return value.length >= 16 ? value.slice(0, 16) : value;
};

const splitEmails = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

const jsonText = (value: unknown) => JSON.stringify(value, null, 2);

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [actions, setActions] = useState<PendingAction[]>([]);
  const [audit, setAudit] = useState<AuditLog[]>([]);
  const [selectedFolder, setSelectedFolder] = useState("inbox");
  const [activeView, setActiveView] = useState("mail");
  const [status, setStatus] = useState("Ready");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sendForm, setSendForm] = useState({ to: "", cc: "", subject: "", body: "" });
  const [eventForm, setEventForm] = useState({
    subject: "",
    body: "",
    start: "",
    end: "",
    location: "",
    attendees: ""
  });
  const [selectedEventId, setSelectedEventId] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);

  const pendingCount = useMemo(
    () => actions.filter((action) => action.status === "pending").length,
    [actions]
  );

  const loadMe = useCallback(async () => {
    try {
      const me = await api.me();
      setUser(me);
      setStatus(me.connected ? "Outlook connected" : "Connect Outlook to begin");
    } catch {
      setUser(null);
      setStatus("Connect Outlook to begin");
    }
  }, []);

  const loadWorkspace = useCallback(async () => {
    if (!user?.connected) return;
    setBusy(true);
    setError("");
    try {
      const [folderData, messageData, eventData, actionData, auditData] = await Promise.all([
        api.folders(),
        api.messages(selectedFolder),
        api.events(),
        api.actions(),
        api.audit(),
        api.chatHistory()
      ]);
      setFolders(folderData.folders);
      setMessages(messageData.messages);
      setEvents(eventData.events);
      setActions(actionData);
      setAudit(auditData);
      setChatHistory(chatHistoryData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load Outlook workspace.");
    } finally {
      setBusy(false);
    }
  }, [selectedFolder, user?.connected]);

  useEffect(() => {
    void loadMe();
  }, [loadMe]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const connect = () => {
    // Using a direct link instead of fetch ensures the session cookie is set 
    // during a top-level navigation, avoiding cross-site fetch restrictions.
    window.location.href = `${api.baseUrl}/auth/microsoft/login?redirect=true`;
  };

  const logout = async () => {
    await api.logout();
    setUser(null);
    setFolders([]);
    setMessages([]);
    setEvents([]);
    setActions([]);
    setAudit([]);
    setSelectedMessage(null);
  };

  const chooseMessage = async (id: string) => {
    setBusy(true);
    setError("");
    try {
      const result = await api.message(id);
      setSelectedMessage(result.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load message.");
    } finally {
      setBusy(false);
    }
  };

  const submitSend = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.sendMail({
        to: splitEmails(sendForm.to),
        cc: splitEmails(sendForm.cc),
        subject: sendForm.subject,
        body: sendForm.body
      });
      setSendForm({ to: "", cc: "", subject: "", body: "" });
      setStatus("Mail sent");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send mail.");
    } finally {
      setBusy(false);
    }
  };

  const resetEventForm = () => {
    setSelectedEventId("");
    setEventForm({ subject: "", body: "", start: "", end: "", location: "", attendees: "" });
  };

  const editEvent = (item: CalendarEvent) => {
    setSelectedEventId(item.id);
    setEventForm({
      subject: item.subject || "",
      body: item.bodyPreview || "",
      start: inputDateTime(item.start?.dateTime),
      end: inputDateTime(item.end?.dateTime),
      location: item.location?.displayName || "",
      attendees: ""
    });
  };

  const submitEvent = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = {
        subject: eventForm.subject,
        body: eventForm.body,
        start: eventForm.start,
        end: eventForm.end,
        location: eventForm.location,
        attendees: splitEmails(eventForm.attendees)
      };
      if (selectedEventId) {
        await api.updateEvent(selectedEventId, payload);
        setStatus("Event updated");
      } else {
        await api.createEvent(payload);
        setStatus("Event created");
      }
      resetEventForm();
      const eventData = await api.events();
      setEvents(eventData.events);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save event.");
    } finally {
      setBusy(false);
    }
  };

  const cancelEvent = async (id: string) => {
    setBusy(true);
    setError("");
    try {
      await api.cancelEvent(id);
      setStatus("Event cancelled");
      const eventData = await api.events();
      setEvents(eventData.events);
      if (selectedEventId === id) {
        resetEventForm();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not cancel event.");
    } finally {
      setBusy(false);
    }
  };

  const sendChatMessage = async (event: FormEvent) => {
    event.preventDefault();
    if (!chatInput.trim() || chatBusy) return;

    const userMessage = chatInput.trim();
    setChatInput("");
    setChatBusy(true);

    // Optimistic update for user message
    const tempId = Math.random().toString();
    setChatHistory((prev) => [
      ...prev,
      { id: tempId, role: "user", content: userMessage, created_at: new Date().toISOString() }
    ]);

    try {
      const result = await api.chat(userMessage);
      setChatHistory((prev) => [...prev.filter((m) => m.id !== tempId), result]);
      // If the LLM called a tool, refresh actions
      if (result.content.toLowerCase().includes("pending") || result.content.toLowerCase().includes("tool")) {
        const actionData = await api.actions();
        setActions(actionData);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send chat message.");
    } finally {
      setChatBusy(false);
    }
  };

  const decideAction = async (id: string, decision: "approve" | "reject") => {
    setBusy(true);
    setError("");
    try {
      if (decision === "approve") {
        await api.approveAction(id);
      } else {
        await api.rejectAction(id);
      }
      const [actionData, auditData] = await Promise.all([api.actions(), api.audit()]);
      setActions(actionData);
      setAudit(auditData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update action.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Outlook Connector</p>
          <h1>Mail, calendar, and agent approvals.</h1>
        </div>
        <div className="account-box">
          <span className={user?.connected ? "status-dot live" : "status-dot"} />
          <span>{user?.email ?? "No account connected"}</span>
          {user ? (
            <button type="button" className="ghost-button" onClick={logout}>
              Sign out
            </button>
          ) : null}
        </div>
      </header>

      {error ? <div className="notice error">{error}</div> : null}
      <div className="notice">{busy ? "Working..." : status}</div>

      {!user?.connected ? (
        <section className="connect-plane">
          <div className="connect-copy">
            <p className="eyebrow">Microsoft Graph OAuth</p>
            <h2>Connect one Outlook account and keep every action auditable.</h2>
            <p>
              Sign in with Microsoft to load delegated mail and calendar access. Write actions from
              MCP tools wait here for approval.
            </p>
            <button type="button" onClick={connect} disabled={busy}>
              Connect Outlook
            </button>
          </div>
          <img
            src="https://th.bing.com/th/id/OIP.51hK5nt_DOczOi_epN9B6QHaEK?o=7rm=3&rs=1&pid=ImgDetMain&o=7&rm=3https://tse4.mm.bing.net/th/id/OIP.sbnvFrmYd5MJRky0_VqTegHaG4?rs=1&pid=ImgDetMain&o=7&rm=3"
            alt="Microsoft Outlook Logo"
          />
        </section>
      ) : (
        <section className="workspace">
          <nav className="rail" aria-label="Workspace">
            {["mail", "calendar", "agent", "approvals", "audit"].map((item) => (
              <button
                key={item}
                type="button"
                className={activeView === item ? "rail-link active" : "rail-link"}
                onClick={() => setActiveView(item)}
              >
                {item === "approvals" ? `approvals ${pendingCount}` : item}
              </button>
            ))}
          </nav>

          {activeView === "mail" ? (
            <section className="surface two-column">
              <div>
                <div className="section-head">
                  <h2>Mailbox</h2>
                  <button type="button" className="ghost-button" onClick={loadWorkspace}>
                    Refresh
                  </button>
                </div>
                <label>
                  Folder
                  <select value={selectedFolder} onChange={(event) => setSelectedFolder(event.target.value)}>
                    <option value="inbox">Inbox</option>
                    {folders.map((folder) => (
                      <option key={folder.id} value={folder.id}>
                        {folder.displayName}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="list-stack">
                  {messages.map((message) => (
                    <button
                      type="button"
                      key={message.id}
                      className="list-row"
                      onClick={() => chooseMessage(message.id)}
                    >
                      <strong>{message.subject || "No subject"}</strong>
                      <span>{message.from?.emailAddress?.address || "Unknown sender"}</span>
                      <small>{message.bodyPreview || "No preview"}</small>
                    </button>
                  ))}
                </div>
              </div>
              <div className="detail-pane">
                <h2>Message detail</h2>
                {selectedMessage ? (
                  <>
                    <h3>{selectedMessage.subject || "No subject"}</h3>
                    <p>{selectedMessage.from?.emailAddress?.address}</p>
                    <pre>{selectedMessage.body?.content || selectedMessage.bodyPreview}</pre>
                  </>
                ) : (
                  <p>Select a message to read the body.</p>
                )}
                <form onSubmit={submitSend} className="form-stack">
                  <h2>Send mail</h2>
                  <input
                    placeholder="To, comma separated"
                    value={sendForm.to}
                    onChange={(event) => setSendForm({ ...sendForm, to: event.target.value })}
                  />
                  <input
                    placeholder="Cc"
                    value={sendForm.cc}
                    onChange={(event) => setSendForm({ ...sendForm, cc: event.target.value })}
                  />
                  <input
                    placeholder="Subject"
                    value={sendForm.subject}
                    onChange={(event) => setSendForm({ ...sendForm, subject: event.target.value })}
                  />
                  <textarea
                    placeholder="Message"
                    value={sendForm.body}
                    onChange={(event) => setSendForm({ ...sendForm, body: event.target.value })}
                  />
                  <button type="submit" disabled={busy}>
                    Send
                  </button>
                </form>
              </div>
            </section>
          ) : null}

          {activeView === "calendar" ? (
            <section className="surface two-column">
              <div>
                <div className="section-head">
                  <h2>Calendar</h2>
                  <button type="button" className="ghost-button" onClick={loadWorkspace}>
                    Refresh
                  </button>
                </div>
                <div className="list-stack">
                  {events.map((item) => (
                    <article key={item.id} className="list-row passive">
                      <strong>{item.subject || "Untitled event"}</strong>
                      <span>{formatDate(item.start?.dateTime)}</span>
                      <small>{item.location?.displayName || "No location"}</small>
                      <div className="row-actions">
                        <button type="button" className="ghost-button" onClick={() => editEvent(item)}>
                          Edit
                        </button>
                        <button type="button" className="danger-button" onClick={() => cancelEvent(item.id)}>
                          Cancel
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
              <form onSubmit={submitEvent} className="detail-pane form-stack">
                <div className="section-head">
                  <h2>{selectedEventId ? "Update event" : "Create event"}</h2>
                  {selectedEventId ? (
                    <button type="button" className="ghost-button" onClick={resetEventForm}>
                      Clear
                    </button>
                  ) : null}
                </div>
                <input
                  placeholder="Subject"
                  value={eventForm.subject}
                  onChange={(event) => setEventForm({ ...eventForm, subject: event.target.value })}
                />
                <textarea
                  placeholder="Body"
                  value={eventForm.body}
                  onChange={(event) => setEventForm({ ...eventForm, body: event.target.value })}
                />
                <input
                  type="datetime-local"
                  value={eventForm.start}
                  onChange={(event) => setEventForm({ ...eventForm, start: event.target.value })}
                />
                <input
                  type="datetime-local"
                  value={eventForm.end}
                  onChange={(event) => setEventForm({ ...eventForm, end: event.target.value })}
                />
                <input
                  placeholder="Location"
                  value={eventForm.location}
                  onChange={(event) => setEventForm({ ...eventForm, location: event.target.value })}
                />
                <input
                  placeholder="Attendees, comma separated"
                  value={eventForm.attendees}
                  onChange={(event) => setEventForm({ ...eventForm, attendees: event.target.value })}
                />
                <button type="submit" disabled={busy}>
                  {selectedEventId ? "Update event" : "Create event"}
                </button>
              </form>
            </section>
          ) : null}

          {activeView === "agent" ? (
            <section className="surface agent-full">
              <div className="chat-pane full-width">
                <div className="section-head">
                  <h2>AI Agent Chat</h2>
                  <p className="eyebrow">Gemini 2.5 Flash</p>
                </div>
                <div className="chat-window">
                  {chatHistory.length === 0 ? (
                    <div className="chat-empty">
                      <p>Ask me to list your emails, summarize meetings, or schedule new events.</p>
                    </div>
                  ) : (
                    chatHistory.map((msg) => (
                      <div key={msg.id} className={`chat-bubble ${msg.role}`}>
                        <div className="bubble-content">{msg.content}</div>
                        <small className="bubble-meta">{formatDate(msg.created_at)}</small>
                      </div>
                    ))
                  )}
                  {chatBusy ? (
                    <div className="chat-bubble assistant thinking">
                      <div className="bubble-content">Agent is thinking...</div>
                    </div>
                  ) : null}
                </div>
                <form onSubmit={sendChatMessage} className="chat-input-row">
                  <input
                    placeholder="Ask the agent anything..."
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    disabled={chatBusy}
                  />
                  <button type="submit" disabled={chatBusy || !chatInput.trim()}>
                    Send
                  </button>
                </form>
              </div>
            </section>
          ) : null}

          {activeView === "approvals" ? (
            <section className="surface">
              <div className="section-head">
                <h2>Pending approvals</h2>
                <button type="button" className="ghost-button" onClick={loadWorkspace}>
                  Refresh
                </button>
              </div>
              <div className="list-stack">
                {actions.map((action) => (
                  <article key={action.id} className="approval-row">
                    <div>
                      <strong>{action.tool_name}</strong>
                      <span>{action.status}</span>
                      <pre>{jsonText(action.payload)}</pre>
                    </div>
                    {action.status === "pending" ? (
                      <div className="approval-actions">
                        <button type="button" onClick={() => decideAction(action.id, "approve")}>
                          Approve
                        </button>
                        <button
                          type="button"
                          className="danger-button"
                          onClick={() => decideAction(action.id, "reject")}
                        >
                          Reject
                        </button>
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {activeView === "audit" ? (
            <section className="surface">
              <div className="section-head">
                <h2>Audit history</h2>
                <button type="button" className="ghost-button" onClick={loadWorkspace}>
                  Refresh
                </button>
              </div>
              <div className="list-stack">
                {audit.map((log) => (
                  <article key={log.id} className="list-row passive">
                    <strong>{log.action}</strong>
                    <span>{log.actor} at {formatDate(log.created_at)}</span>
                    <small>{log.target || "No target"}</small>
                  </article>
                ))}
              </div>
            </section>
          ) : null}
        </section>
      )}
    </main>
  );
}

export default App;
