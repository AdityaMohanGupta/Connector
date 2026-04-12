import type { AgentToolResult, AuditLog, CalendarEvent, Folder, Message, PendingAction, User } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {})
    },
    ...init
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // Keep the HTTP status text.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return {} as T;
  }
  return (await response.json()) as T;
}

export const api = {
  baseUrl: API_BASE,
  me: () => request<User>("/auth/me"),
  login: () => request<{ authorization_url: string }>("/auth/microsoft/login"),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  folders: () => request<{ folders: Folder[] }>("/outlook/folders"),
  messages: (folderId: string, top = 20) =>
    request<{ messages: Message[] }>(`/outlook/messages?folder_id=${encodeURIComponent(folderId)}&top=${top}`),
  message: (id: string) => request<{ message: Message }>(`/outlook/messages/${encodeURIComponent(id)}`),
  sendMail: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>("/outlook/send", { method: "POST", body: JSON.stringify(payload) }),
  events: (top = 20) => request<{ events: CalendarEvent[] }>(`/outlook/events?top=${top}`),
  createEvent: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>("/outlook/events", { method: "POST", body: JSON.stringify(payload) }),
  updateEvent: (id: string, payload: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/outlook/events/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  cancelEvent: (id: string) =>
    request<Record<string, unknown>>(`/outlook/events/${encodeURIComponent(id)}`, { method: "DELETE" }),
  invokeTool: (toolName: string, args: Record<string, unknown>) =>
    request<AgentToolResult>(`/agent/tools/${toolName}`, {
      method: "POST",
      body: JSON.stringify({ arguments: args })
    }),
  actions: () => request<PendingAction[]>("/agent/actions"),
  approveAction: (id: string) =>
    request<PendingAction>(`/agent/actions/${id}/approve`, { method: "POST" }),
  rejectAction: (id: string) =>
    request<PendingAction>(`/agent/actions/${id}/reject`, { method: "POST" }),
  audit: () => request<AuditLog[]>("/agent/audit")
};
