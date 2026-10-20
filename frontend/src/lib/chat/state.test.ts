import assert from "node:assert/strict";
import { test } from "node:test";

import type { ChatReply } from "./client.ts";
import { INITIAL_STATE, chatReducer, loadState, saveState, type ChatState } from "./state.ts";

const session = { conversationId: "c1", token: "t" };
const greeting: ChatReply = { text: "Hello!", language: "en", options: [], pending_action: null, error: null };
const offer: ChatReply = {
  ...greeting,
  text: "Free times:",
  options: [{ number: 1, start: "2030-01-07T09:00:00+01:00", end: "2030-01-07T09:30:00+01:00", dentist: "Dr. A" }],
};
const proposal: ChatReply = { ...greeting, text: "Please confirm", pending_action: { id: "p1", type: "book" } };

function run(...actions: Parameters<typeof chatReducer>[1][]): ChatState {
  return actions.reduce(chatReducer, INITIAL_STATE);
}

test("a conversation starts with the greeting", () => {
  const state = run({ type: "starting" }, { type: "started", session, reply: greeting });
  assert.deepEqual(state.session, session);
  assert.equal(state.messages[0].text, "Hello!");
  assert.equal(state.status, "idle");
});

test("only the newest assistant message keeps options and pending actions", () => {
  const state = run(
    { type: "started", session, reply: offer },
    { type: "sending", outgoing: { message: "1" }, display: "1" },
    { type: "replied", reply: proposal },
  );
  assert.deepEqual(state.messages.map((m) => m.role), ["assistant", "user", "assistant"]);
  assert.deepEqual(state.messages[0].options, []);
  assert.deepEqual(state.messages[2].pendingAction, { id: "p1", type: "book" });
  const confirmed = run(
    { type: "started", session, reply: proposal },
    { type: "sending", outgoing: { confirm_action: "p1" }, display: null },
  );
  assert.equal(confirmed.messages.length, 1);
  assert.equal(confirmed.messages[0].pendingAction, null);
});

test("an offline assistant reply is flagged", () => {
  const state = run({ type: "started", session, reply: { ...greeting, error: "assistant_unavailable" } });
  assert.equal(state.messages[0].offline, true);
});

test("failures keep a retry; an expired chat drops the session", () => {
  const busy = run({ type: "started", session, reply: greeting }, { type: "failed", error: "busy", retry: { message: "hi" } });
  assert.deepEqual(busy.retry, { message: "hi" });
  assert.deepEqual(busy.session, session);
  const expired = run({ type: "started", session, reply: greeting }, { type: "failed", error: "expired", retry: null });
  assert.equal(expired.session, null);
  assert.equal(expired.error, "expired");
});

test("state survives in session storage only while a conversation exists", () => {
  const store = new Map<string, string>();
  const storage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  };
  const state = run({ type: "started", session, reply: greeting }, { type: "sending", outgoing: { message: "x" }, display: "x" });
  saveState(storage, state);
  const restored = loadState(storage);
  assert.equal(restored?.messages.length, 2);
  assert.equal(restored?.status, "idle");
  saveState(storage, INITIAL_STATE);
  assert.equal(loadState(storage), null);
  assert.equal(loadState({ getItem: () => "{not json" }), null);
  assert.equal(loadState(undefined), null);
});
