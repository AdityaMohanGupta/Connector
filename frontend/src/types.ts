export type User = {
  id: string;
  email: string;
  display_name: string;
  connected: boolean;
};

export type Folder = {
  id: string;
  displayName: string;
  totalItemCount?: number;
  unreadItemCount?: number;
};

export type Message = {
  id: string;
  subject?: string;
  from?: { emailAddress?: { name?: string; address?: string } };
  receivedDateTime?: string;
  isRead?: boolean;
  bodyPreview?: string;
  body?: { contentType?: string; content?: string };
};

export type CalendarEvent = {
  id: string;
  subject?: string;
  bodyPreview?: string;
  start?: { dateTime?: string; timeZone?: string };
  end?: { dateTime?: string; timeZone?: string };
  location?: { displayName?: string };
};

export type PendingAction = {
  id: string;
  tool_name: string;
  action_type: string;
  payload: Record<string, unknown>;
  status: string;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  decided_at: string | null;
};

export type AuditLog = {
  id: string;
  actor: string;
  action: string;
  target: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type AgentToolResult = {
  status: "completed" | "pending_approval" | "error";
  tool_name: string;
  data: Record<string, unknown>;
  pending_action_id?: string;
  message: string;
};
