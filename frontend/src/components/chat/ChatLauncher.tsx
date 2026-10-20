"use client";

import dynamic from "next/dynamic";

import { Icon } from "@/components/ui/Icon";

import { useChat } from "./ChatProvider";

// The conversation UI is only downloaded when the chat is first opened.
const ChatPanel = dynamic(() => import("./ChatPanel").then((m) => m.ChatPanel), { ssr: false });

export function ChatLauncher() {
  const { isOpen, open, close, t, clinic, launcher } = useChat();
  if (!clinic.slug) return null;
  return (
    <>
      <button
        ref={launcher}
        type="button"
        onClick={isOpen ? close : open}
        aria-expanded={isOpen}
        aria-controls="chat-panel"
        className={`fixed right-4 bottom-4 z-50 inline-flex h-14 items-center gap-3 rounded-full bg-forest pr-6 pl-5 text-ivory shadow-[0_18px_40px_-16px_rgba(20,42,33,0.6)] transition hover:bg-forest-deep sm:right-6 sm:bottom-6 ${
          isOpen ? "max-sm:hidden" : ""
        }`}
      >
        <Icon name={isOpen ? "close" : "chat"} className="h-5 w-5" />
        <span className="text-sm font-medium">
          <span className="sm:hidden">{isOpen ? t.close : t.openShort}</span>
          <span className="max-sm:hidden">{isOpen ? t.close : t.open}</span>
        </span>
      </button>
      {isOpen && <ChatPanel />}
    </>
  );
}
