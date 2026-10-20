"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { Icon } from "@/components/ui/Icon";
import type { SlotOption } from "@/lib/chat/client";
import type { ChatMessage } from "@/lib/chat/state";
import { formatDate, formatTime, interpolate } from "@/lib/format";
import { LANGUAGE_NAMES, LOCALES, isLocale, type Locale } from "@/lib/locale";

import { useChat } from "./ChatProvider";

const MAX_LENGTH = 1000; // backend: apps/chatbot/views.py MAX_MESSAGE_CHARS

/** The backend lists options as "1. …" lines; they are shown as buttons instead. */
function visibleText(message: ChatMessage): string {
  if (!message.options.length) return message.text;
  return message.text
    .split("\n")
    .filter((line) => !message.options.some((o) => line.startsWith(`${o.number}. `)))
    .join("\n")
    .trim();
}

export function ChatPanel() {
  const chat = useChat();
  const { state, t, clinic, language } = chat;
  const [draft, setDraft] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);
  const list = useRef<HTMLOListElement>(null);
  const busy = state.status !== "idle";
  const uiLocale: Locale = isLocale(language) ? language : "en";

  useEffect(() => input.current?.focus(), []);
  useEffect(() => {
    list.current?.scrollTo({ top: list.current.scrollHeight, behavior: "smooth" });
  }, [state.messages.length, state.status]);

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    void chat.sendText(text.slice(0, MAX_LENGTH));
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  const optionLabel = (option: SlotOption) =>
    `${formatDate(option.start, uiLocale, clinic.timezone, "short")}, ${formatTime(option.start, uiLocale, clinic.timezone)} · ${option.dentist}`;

  const offline = state.messages.at(-1)?.offline;

  return (
    <section
      id="chat-panel"
      role="dialog"
      aria-modal="false"
      aria-labelledby="chat-title"
      onKeyDown={(event) => event.key === "Escape" && chat.close()}
      className="fixed inset-0 z-50 flex flex-col bg-paper sm:inset-auto sm:right-6 sm:bottom-24 sm:h-[min(680px,calc(100dvh-8rem))] sm:w-[400px] sm:rounded-2xl sm:border sm:border-line sm:shadow-[0_30px_70px_-24px_rgba(20,42,33,0.45)]"
    >
      <header className="border-b border-line px-5 pt-4 pb-3">
        <div className="flex items-center justify-between gap-3">
          <h2 id="chat-title" className="text-2xl leading-none text-forest">
            {t.title}
          </h2>
          <div className="flex items-center gap-1">
            <label className="sr-only" htmlFor="chat-language">
              {t.language}
            </label>
            <select
              id="chat-language"
              value={language}
              onChange={(event) => isLocale(event.target.value) && chat.setLanguage(event.target.value)}
              className="h-9 rounded-full border border-line bg-paper px-2 text-xs"
            >
              {LOCALES.map((code) => (
                <option key={code} value={code} lang={code}>
                  {LANGUAGE_NAMES[code]}
                </option>
              ))}
            </select>
            <button type="button" onClick={() => void chat.newChat()} title={t.newChat} className="rounded-full p-2 text-muted hover:bg-sand hover:text-forest">
              <Icon name="refresh" className="h-4.5 w-4.5" />
              <span className="sr-only">{t.newChat}</span>
            </button>
            <button type="button" onClick={() => void chat.deleteChat()} title={t.deleteChat} className="rounded-full p-2 text-muted hover:bg-sand hover:text-forest">
              <Icon name="trash" className="h-4.5 w-4.5" />
              <span className="sr-only">{t.deleteChat}</span>
            </button>
            <button type="button" onClick={chat.close} title={t.close} className="rounded-full p-2 text-muted hover:bg-sand hover:text-forest">
              <Icon name="close" className="h-5 w-5" />
              <span className="sr-only">{t.close}</span>
            </button>
          </div>
        </div>
        <p className="mt-1.5 text-xs text-muted">{interpolate(t.subtitle, { clinic: clinic.name })}</p>
      </header>

      <p className="border-b border-line bg-ivory px-5 py-2.5 text-[11px] leading-snug text-muted">{t.disclaimer}</p>

      <ol ref={list} aria-live="polite" aria-relevant="additions" className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
        {state.messages.map((message) => (
          <li key={message.id} className={message.role === "user" ? "flex justify-end" : "flex flex-col items-start"}>
            <p className="sr-only">{message.role === "user" ? t.you : t.assistant}:</p>
            <p
              className={`max-w-[88%] rounded-2xl px-4 py-3 text-[15px] leading-relaxed whitespace-pre-line ${
                message.role === "user" ? "rounded-br-sm bg-forest text-ivory" : "rounded-tl-sm bg-ivory text-ink"
              }`}
            >
              {visibleText(message)}
            </p>
            {message.options.length > 0 && (
              <div className="mt-3 w-full" role="group" aria-label={t.chooseTime}>
                <ul className="space-y-2">
                  {message.options.map((option) => (
                    <li key={option.number}>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void chat.sendText(String(option.number))}
                        className="w-full rounded-xl border border-line bg-paper px-4 py-2.5 text-left text-sm transition hover:border-forest hover:bg-ivory disabled:opacity-50"
                      >
                        <span className="mr-2 font-medium text-brass tabular-nums">{option.number}</span>
                        {optionLabel(option)}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {message.pendingAction && (
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void chat.confirm(message.pendingAction!.id)}
                  className="min-h-11 rounded-full bg-forest px-5 text-sm font-medium text-ivory hover:bg-forest-deep disabled:opacity-50"
                >
                  {t.confirm[message.pendingAction.type]}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void chat.decline()}
                  className="min-h-11 rounded-full border border-line px-5 text-sm text-ink hover:border-forest disabled:opacity-50"
                >
                  {t.decline}
                </button>
              </div>
            )}
          </li>
        ))}
        {busy && (
          <li className="flex items-center gap-2 text-sm text-muted" role="status">
            <span className="flex gap-1" aria-hidden="true">
              {[0, 1, 2].map((i) => (
                <span key={i} className="h-1.5 w-1.5 animate-pulse rounded-full bg-brass" style={{ animationDelay: `${i * 150}ms` }} />
              ))}
            </span>
            {state.status === "starting" ? t.starting : t.typing}
          </li>
        )}
      </ol>

      {(offline || state.error || chat.notice) && (
        <div role="alert" className="mx-5 mb-3 rounded-xl border border-brass/40 bg-ivory px-4 py-3 text-sm">
          {offline && (
            <p>
              {t.offline}{" "}
              {clinic.phone && (
                <a className="font-medium text-forest underline" href={`tel:${clinic.phone.replace(/\s/g, "")}`}>
                  {clinic.phone}
                </a>
              )}
            </p>
          )}
          {state.error && (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p>{t.errors[state.error]}</p>
              {state.error === "expired" ? (
                <button type="button" onClick={() => void chat.newChat()} className="font-medium text-forest underline">
                  {t.newChat}
                </button>
              ) : (
                <button type="button" onClick={() => void chat.retry()} className="font-medium text-forest underline">
                  {t.retry}
                </button>
              )}
            </div>
          )}
          {chat.notice && !state.error && (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p>{chat.notice}</p>
              <button type="button" onClick={() => void chat.newChat()} className="font-medium text-forest underline">
                {t.start}
              </button>
            </div>
          )}
        </div>
      )}

      <form onSubmit={submit} className="flex items-end gap-2 border-t border-line p-4">
        <label htmlFor="chat-input" className="sr-only">
          {t.placeholder}
        </label>
        <textarea
          ref={input}
          id="chat-input"
          rows={1}
          value={draft}
          maxLength={MAX_LENGTH}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder={t.placeholder}
          className="max-h-32 min-h-11 flex-1 resize-none rounded-2xl border border-line bg-ivory px-4 py-2.5 text-[15px] leading-relaxed placeholder:text-muted/80 focus:border-forest focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy || !draft.trim()}
          className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-forest text-ivory hover:bg-forest-deep disabled:opacity-40"
        >
          <Icon name="send" className="h-5 w-5" />
          <span className="sr-only">{t.send}</span>
        </button>
      </form>
    </section>
  );
}
