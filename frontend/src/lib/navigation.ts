import type { Dictionary } from "@/dictionaries";

export const PAGES = ["", "services", "dentists", "about", "faq", "contact", "book"] as const;
export type PagePath = (typeof PAGES)[number];

/** Main navigation entries ("book" is shown as a separate button). */
export function navItems(t: Dictionary["nav"]): { path: PagePath; label: string }[] {
  return [
    { path: "", label: t.home },
    { path: "services", label: t.services },
    { path: "dentists", label: t.dentists },
    { path: "about", label: t.about },
    { path: "faq", label: t.faq },
    { path: "contact", label: t.contact },
  ];
}

export function href(locale: string, path: PagePath | string): string {
  return path ? `/${locale}/${path}` : `/${locale}`;
}
