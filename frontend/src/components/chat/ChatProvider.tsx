"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState, type ReactNode, type RefObject } from "react";

import type { Dictionary } from "@/dictionaries";
import {
  ChatError,
  deleteConversation,
  sendMessage,
  startConversation,
  type ChatErrorKind,
  type ChatSession,
  type Outgoing,
} from "@/lib/chat/client";
import { chatReducer, INITIAL_STATE, loadState, saveState, type ChatState } from "@/lib/chat/state";
import type { Locale } from "@/lib/locale";

type ClinicInfo = { slug: string | null; name: string; phone: string; timezone: string };

type ChatContextValue = {
  state: ChatState;
  isOpen: boolean;
  language: Locale;
  notice: string | null;
  clinic: ClinicInfo;
  t: Dictionary["chat"];
  launcher: RefObject<HTMLButtonElement | null>;
  open: () => void;
  close: () => void;
  setLanguage: (language: Locale) => void;
  sendText: (text: string) => Promise<void>;
  confirm: (actionId: string) => Promise<void>;
  decline: () => Promise<void>;
  retry: () => Promise<void>;
  newChat: () => Promise<void>;
  deleteChat: () => Promise<void>;
  /** Open the chat and send a prepared message (used by the booking page). */
  handoff: (text: string) => Promise<void>;
};

const ChatContext = createContext<ChatContextValue | null>(null);

export function useChat(): ChatContextValue {
  const value = useContext(ChatContext);
  if (!value) throw new Error("useChat must be used inside <ChatProvider>.");
  return value;
}

function kindOf(error: unknown): ChatErrorKind {
  return error instanceof ChatError ? error.kind : "server";
}

function sessionStore(): Storage | undefined {
  try {
    return window.sessionStorage;
  } catch {
    return undefined;
  }
}

type Props = { children: ReactNode; locale: Locale; t: Dictionary["chat"]; clinic: ClinicInfo };

export function ChatProvider({ children, locale, t, clinic }: Props) {
  const [state, dispatch] = useReducer(chatReducer, INITIAL_STATE);
  const [isOpen, setOpen] = useState(false);
  const [language, setLanguageState] = useState<Locale>(locale);
  const [notice, setNotice] = useState<string | null>(null);
  const launcher = useRef<HTMLButtonElement>(null);
  const latest = useRef(state);
  const restored = useRef(false);

  useEffect(() => {
    latest.current = state;
    if (!restored.current) {
      // Restore once after hydration; the server never renders chat state.
      restored.current = true;
      const saved = loadState(sessionStore());
      if (saved) dispatch({ type: "restore", state: saved });
      return;
    }
    saveState(sessionStore(), state);
  }, [state]);

  const start = useCallback(
    async (chatLanguage: Locale): Promise<ChatSession | null> => {
      if (!clinic.slug) return null;
      dispatch({ type: "starting" });
      try {
        const { session, reply } = await startConversation(clinic.slug, chatLanguage);
        dispatch({ type: "started", session, reply });
        latest.current = { ...latest.current, session };
        return session;
      } catch (error) {
        dispatch({ type: "failed", error: kindOf(error), retry: null });
        return null;
      }
    },
    [clinic.slug],
  );

  const send = useCallback(
    async (outgoing: Outgoing, display: string | null) => {
      setNotice(null);
      const session = latest.current.session ?? (await start(language));
      if (!session) return;
      dispatch({ type: "sending", outgoing, display });
      try {
        dispatch({ type: "replied", reply: await sendMessage(session, outgoing) });
      } catch (error) {
        dispatch({ type: "failed", error: kindOf(error), retry: outgoing });
      }
    },
    [language, start],
  );

  const discard = useCallback(async () => {
    const session = latest.current.session;
    dispatch({ type: "reset" });
    latest.current = INITIAL_STATE;
    if (session) {
      try {
        await deleteConversation(session);
      } catch {
        // The conversation expires and is purged on the server anyway.
      }
    }
  }, []);

  const value = useMemo<ChatContextValue>(
    () => ({
      state,
      isOpen,
      language,
      notice,
      clinic,
      t,
      launcher,
      open: () => {
        setOpen(true);
        if (!latest.current.session && latest.current.status === "idle") void start(language);
      },
      close: () => {
        setOpen(false);
        launcher.current?.focus();
      },
      setLanguage: (next) => {
        setLanguageState(next);
        // Only the greeting so far: restart so it appears in the chosen language.
        const onlyGreeting = latest.current.messages.every((m) => m.role === "assistant");
        if (onlyGreeting) void discard().then(() => start(next));
      },
      sendText: (text) => send({ message: text }, text),
      confirm: (actionId) => send({ confirm_action: actionId }, null),
      decline: () => send({ message: t.declineWord }, t.decline),
      retry: async () => {
        const pending = latest.current.retry;
        if (pending) await send(pending, null);
        else await start(language);
      },
      newChat: async () => {
        setNotice(null);
        await discard();
        await start(language);
      },
      deleteChat: async () => {
        await discard();
        setNotice(t.deleted);
      },
      handoff: async (text) => {
        setOpen(true);
        await send({ message: text }, text);
      },
    }),
    [state, isOpen, language, notice, clinic, t, start, send, discard],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}
