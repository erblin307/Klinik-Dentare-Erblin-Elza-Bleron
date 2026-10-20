import type { ChatErrorKind, ChatReply, ChatSession, Outgoing, PendingAction, SlotOption } from "./client.ts";

export type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  text: string;
  options: SlotOption[];
  pendingAction: PendingAction | null;
  offline: boolean;
};

export type ChatState = {
  session: ChatSession | null;
  messages: ChatMessage[];
  status: "idle" | "starting" | "sending";
  error: ChatErrorKind | null;
  retry: Outgoing | null; // what to send again after a failure
};

export type ChatAction =
  | { type: "starting" }
  | { type: "started"; session: ChatSession; reply: ChatReply }
  | { type: "sending"; outgoing: Outgoing; display: string | null }
  | { type: "replied"; reply: ChatReply }
  | { type: "failed"; error: ChatErrorKind; retry: Outgoing | null }
  | { type: "reset" }
  | { type: "restore"; state: ChatState };

export const INITIAL_STATE: ChatState = { session: null, messages: [], status: "idle", error: null, retry: null };

/** Only the newest assistant message keeps its slot options and pending action. */
function withoutActions(messages: ChatMessage[]): ChatMessage[] {
  return messages.map((m) => (m.options.length || m.pendingAction ? { ...m, options: [], pendingAction: null } : m));
}

function assistantMessage(id: number, reply: ChatReply): ChatMessage {
  return {
    id,
    role: "assistant",
    text: reply.text,
    options: reply.options ?? [],
    pendingAction: reply.pending_action ?? null,
    offline: reply.error === "assistant_unavailable",
  };
}

function nextId(messages: ChatMessage[]): number {
  return messages.length ? messages[messages.length - 1].id + 1 : 1;
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "starting":
      return { ...state, status: "starting", error: null };
    case "started":
      return {
        ...INITIAL_STATE,
        session: action.session,
        messages: [assistantMessage(1, action.reply)],
      };
    case "sending": {
      const messages = withoutActions(state.messages);
      if (action.display !== null) {
        messages.push({ id: nextId(messages), role: "user", text: action.display, options: [], pendingAction: null, offline: false });
      }
      return { ...state, messages, status: "sending", error: null, retry: null };
    }
    case "replied":
      return {
        ...state,
        messages: [...state.messages, assistantMessage(nextId(state.messages), action.reply)],
        status: "idle",
      };
    case "failed":
      return {
        ...state,
        status: "idle",
        error: action.error,
        retry: action.retry,
        // An expired conversation cannot continue; a new one is needed.
        session: action.error === "expired" ? null : state.session,
      };
    case "reset":
      return INITIAL_STATE;
    case "restore":
      return { ...action.state, status: "idle" };
  }
}

const STORAGE_KEY = "clinic-chat:v1";

/** Chat state lives only in this browser tab (sessionStorage) and is cleared with it. */
export function loadState(storage: Pick<Storage, "getItem"> | undefined): ChatState | null {
  try {
    const raw = storage?.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ChatState;
    return Array.isArray(parsed.messages) ? parsed : null;
  } catch {
    return null;
  }
}

export function saveState(storage: Pick<Storage, "setItem" | "removeItem"> | undefined, state: ChatState): void {
  try {
    if (state.session) storage?.setItem(STORAGE_KEY, JSON.stringify({ ...state, status: "idle" }));
    else storage?.removeItem(STORAGE_KEY);
  } catch {
    // Storage may be unavailable (private mode); the chat still works for this page.
  }
}
