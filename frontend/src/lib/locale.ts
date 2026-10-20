export const LOCALES = ["sq", "en", "de"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "sq";

/** BCP 47 tags for Intl formatting (European conventions for English). */
export const INTL_LOCALE: Record<Locale, string> = { sq: "sq-AL", en: "en-GB", de: "de-DE" };

export const LANGUAGE_NAMES: Record<Locale, string> = { sq: "Shqip", en: "English", de: "Deutsch" };

export function isLocale(value: string): value is Locale {
  return (LOCALES as readonly string[]).includes(value);
}

/** Best supported locale for an Accept-Language header, e.g. "de-AT,de;q=0.9,en;q=0.5". */
export function negotiateLocale(acceptLanguage: string | null): Locale {
  if (!acceptLanguage) return DEFAULT_LOCALE;
  const ranked = acceptLanguage
    .split(",")
    .map((part, index) => {
      const [tag, ...params] = part.trim().split(";");
      const q = params.find((p) => p.trim().startsWith("q="));
      return { language: tag.trim().toLowerCase().split("-")[0], q: q ? Number(q.trim().slice(2)) : 1, index };
    })
    .filter((entry) => entry.language && !Number.isNaN(entry.q) && entry.q > 0)
    .sort((a, b) => b.q - a.q || a.index - b.index);
  return ranked.map((entry) => entry.language).find(isLocale) ?? DEFAULT_LOCALE;
}
