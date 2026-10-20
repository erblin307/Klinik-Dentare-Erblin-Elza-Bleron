import type { Locale } from "../lib/locale.ts";
import de from "./de.ts";
import en, { type Dictionary } from "./en.ts";
import sq from "./sq.ts";

export type { Dictionary };

const DICTIONARIES: Record<Locale, Dictionary> = { sq, en, de };

export function getDictionary(locale: Locale): Dictionary {
  return DICTIONARIES[locale];
}
