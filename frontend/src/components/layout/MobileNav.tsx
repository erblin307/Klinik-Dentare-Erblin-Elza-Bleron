"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import type { Locale } from "@/lib/locale";
import type { PagePath } from "@/lib/navigation";

import { LanguageSwitcher } from "./LanguageSwitcher";
import { NavLinks } from "./NavLinks";

type Props = {
  locale: Locale;
  items: { path: PagePath; label: string }[];
  labels: { open: string; close: string; book: string; language: string; primary: string };
};

export function MobileNav({ locale, items, labels }: Props) {
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open]);

  const close = () => setOpen(false);

  return (
    <div className="lg:hidden">
      <button
        ref={button}
        type="button"
        aria-expanded={open}
        aria-controls="mobile-menu"
        onClick={() => setOpen(!open)}
        className="inline-flex h-11 w-11 items-center justify-center rounded-full text-forest hover:bg-sand"
      >
        <Icon name={open ? "close" : "menu"} className="h-6 w-6" />
        <span className="sr-only">{open ? labels.close : labels.open}</span>
      </button>
      {open && (
        <div id="mobile-menu" className="fixed inset-x-0 top-[72px] bottom-0 z-40 overflow-y-auto bg-ivory px-5 pb-10 sm:px-8">
          <nav aria-label={labels.primary} className="pt-2">
            <NavLinks locale={locale} items={items} orientation="vertical" onNavigate={close} />
          </nav>
          <Link
            href={`/${locale}/book`}
            onClick={close}
            className="mt-8 flex min-h-12 items-center justify-center rounded-full bg-forest px-6 text-ivory"
          >
            {labels.book}
          </Link>
          <div className="mt-8 flex justify-center">
            <LanguageSwitcher locale={locale} label={labels.language} />
          </div>
        </div>
      )}
    </div>
  );
}
