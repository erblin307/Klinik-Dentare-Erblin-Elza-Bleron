import assert from "node:assert/strict";
import { test } from "node:test";

import { ChatError, deleteConversation, errorKind, sendMessage, startConversation } from "./client.ts";

type Call = { url: string; init: RequestInit };

function fakeFetch(status: number, body: unknown = {}, calls: Call[] = []): typeof fetch {
  return (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  }) as typeof fetch;
}

const reply = { text: "Hi", language: "en", options: [], pending_action: null, error: null };
const session = { conversationId: "c0ffee", token: "secret-token" };

test("starting posts the language and returns the session and greeting", async () => {
  const calls: Call[] = [];
  const result = await startConversation("smile", "de", fakeFetch(201, { conversation_id: "c0ffee", token: "t", ...reply }, calls));
  assert.equal(calls[0].url, "/api/chat/clinics/smile/conversations");
  assert.equal(calls[0].init.method, "POST");
  assert.deepEqual(JSON.parse(String(calls[0].init.body)), { language: "de" });
  assert.deepEqual(result.session, { conversationId: "c0ffee", token: "t" });
  assert.equal(result.reply.text, "Hi");
});

test("messages and confirmations are sent with the bearer token", async () => {
  const calls: Call[] = [];
  await sendMessage(session, { message: "Hello" }, fakeFetch(200, reply, calls));
  await sendMessage(session, { confirm_action: "act-1" }, fakeFetch(200, reply, calls));
  assert.equal(calls[0].url, "/api/chat/conversations/c0ffee/messages");
  assert.equal((calls[0].init.headers as Record<string, string>).Authorization, "Bearer secret-token");
  assert.deepEqual(JSON.parse(String(calls[1].init.body)), { confirm_action: "act-1" });
});

test("HTTP errors map to error kinds the UI can explain", async () => {
  assert.equal(errorKind(409), "busy");
  assert.equal(errorKind(429), "rateLimited");
  assert.equal(errorKind(404), "expired");
  assert.equal(errorKind(410), "expired");
  assert.equal(errorKind(400), "invalid");
  assert.equal(errorKind(502), "server");
  await assert.rejects(sendMessage(session, { message: "x" }, fakeFetch(429)), (e) => e instanceof ChatError && e.kind === "rateLimited");
  const offline = (async () => {
    throw new TypeError("Failed to fetch");
  }) as unknown as typeof fetch;
  await assert.rejects(sendMessage(session, { message: "x" }, offline), (e) => e instanceof ChatError && e.kind === "network");
});

test("deleting tolerates an already expired conversation", async () => {
  const calls: Call[] = [];
  await deleteConversation(session, fakeFetch(204, null, calls));
  assert.equal(calls[0].init.method, "DELETE");
  await deleteConversation(session, fakeFetch(404));
  await assert.rejects(deleteConversation(session, fakeFetch(500)));
});
