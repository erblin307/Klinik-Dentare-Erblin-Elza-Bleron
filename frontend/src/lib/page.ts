import { notFound } from "next/navigation";

import { getDictionary, type Dictionary } from "@/dictionaries";

import { clinicSlug } from "./api";
import { isLocale, type Locale } from "./locale";

/** Validate the [lang] segment and load its dictionary. */
export async function localeFrom(params: Promise<{ lang: string }>): Promise<{ lang: Locale; t: Dictionary }> {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  return { lang, t: getDictionary(lang) };
}

/** Text shown when clinic data could not be loaded. */
export function unavailableText(t: Dictionary): string {
  return clinicSlug() ? t.common.unavailable : t.common.notConfigured;
}
