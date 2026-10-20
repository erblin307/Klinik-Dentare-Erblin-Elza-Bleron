// Browser client for the existing Django chat API (backend/apps/chatbot/views.py):
//   POST   /api/chat/clinics/<slug>/conversations   -> start, returns id + token + greeting
//   POST   /api/chat/conversations/<id>/messages    -> {"message"} or {"confirm_action"}
//   DELETE /api/chat/conversations/<id>             -> erase the conversation
// Requests go to this site's origin and are forwarded to Django (next.config.ts).

export type PendingAction = { id: string; type: "book" | "cancel" | "reschedule" };
export type SlotOption = { number: number; start: string; end: string; dentist: string };

export type ChatReply = {
  text: string;
  language: string;
  options: SlotOption[];
  pending_action: PendingAction | null;
  error: string | null;
};

export type ChatSession = { conversationId: string; token: string };
export type ChatErrorKind = "network" | "busy" | "rateLimited" | "expired" | "invalid" | "server";
export type Outgoing = { message: string } | { confirm_action: string };

export class ChatError extends Error {
  kind: ChatErrorKind;

  constructor(kind: ChatErrorKind) {
    super(`Chat request failed: ${kind}`);
    this.kind = kind;
  }
}

const BASE = "/api/chat";

export function errorKind(status: number): ChatErrorKind {
  if (status === 409) return "busy";
  if (status === 429) return "rateLimited";
  if (status === 404 || status === 410) return "expired"; // unknown, wrong token or expired
  if (status === 400) return "invalid";
  return "server";
}

async function request(url: string, init: RequestInit, fetchImpl: typeof fetch): Promise<Response> {
  let response: Response;
  try {
    response = await fetchImpl(url, init);
  } catch {
    throw new ChatError("network");
  }
  if (!response.ok) throw new ChatError(errorKind(response.status));
  return response;
}

function authorized(session: ChatSession): Record<string, string> {
  return { Authorization: `Bearer ${session.token}`, "Content-Type": "application/json" };
}

export async function startConversation(
  clinicSlug: string,
  language: string,
  fetchImpl: typeof fetch = fetch,
): Promise<{ session: ChatSession; reply: ChatReply }> {
  const response = await request(
    `${BASE}/clinics/${encodeURIComponent(clinicSlug)}/conversations`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ language }) },
    fetchImpl,
  );
  const { conversation_id, token, ...reply } = await response.json();
  return { session: { conversationId: conversation_id, token }, reply: reply as ChatReply };
}

export async function sendMessage(
  session: ChatSession,
  body: Outgoing,
  fetchImpl: typeof fetch = fetch,
): Promise<ChatReply> {
  const response = await request(
    `${BASE}/conversations/${session.conversationId}/messages`,
    { method: "POST", headers: authorized(session), body: JSON.stringify(body) },
    fetchImpl,
  );
  return (await response.json()) as ChatReply;
}

export async function deleteConversation(session: ChatSession, fetchImpl: typeof fetch = fetch): Promise<void> {
  try {
    await request(`${BASE}/conversations/${session.conversationId}`, { method: "DELETE", headers: authorized(session) }, fetchImpl);
  } catch (error) {
    // Already gone (expired or deleted) is fine; anything else is reported.
    if (!(error instanceof ChatError && error.kind === "expired")) throw error;
  }
}
