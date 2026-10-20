"use client";

import { buttonClasses } from "@/components/ui/ButtonLink";
import { Icon } from "@/components/ui/Icon";

import { useChat } from "./ChatProvider";

export function OpenChatButton({ label, variant = "secondary" }: { label: string; variant?: "primary" | "secondary" | "light" }) {
  const { open, clinic } = useChat();
  if (!clinic.slug) return null;
  return (
    <button type="button" onClick={open} className={buttonClasses(variant)}>
      <Icon name="chat" className="h-4 w-4" />
      {label}
    </button>
  );
}
