import { INTL_LOCALE, type Locale } from "./locale.ts";

// 2024-01-01 was a Monday; the backend numbers weekdays Monday = 0.
const MONDAY = Date.UTC(2024, 0, 1, 12);

export function weekdayName(weekday: number, locale: Locale, style: "long" | "short" = "long"): string {
  const date = new Date(MONDAY + weekday * 86_400_000);
  return new Intl.DateTimeFormat(INTL_LOCALE[locale], { weekday: style, timeZone: "UTC" }).format(date);
}

/** "09:00" for an ISO datetime, shown in the clinic's time zone. */
export function formatTime(iso: string, locale: Locale, timeZone: string): string {
  return new Intl.DateTimeFormat(INTL_LOCALE[locale], {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone,
  }).format(new Date(iso));
}

/** "Monday, 7 January 2030" for an ISO datetime or a YYYY-MM-DD date, in the clinic's time zone. */
export function formatDate(value: string, locale: Locale, timeZone: string, style: "long" | "short" = "long"): string {
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T12:00:00Z`) : new Date(value);
  const zone = /^\d{4}-\d{2}-\d{2}$/.test(value) ? "UTC" : timeZone;
  const options: Intl.DateTimeFormatOptions =
    style === "long"
      ? { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: zone }
      : { weekday: "short", day: "numeric", month: "short", timeZone: zone };
  return new Intl.DateTimeFormat(INTL_LOCALE[locale], options).format(date);
}

/** Price in the clinic's currency, or null when the price is set after consultation. */
export function formatPrice(price: string | null, currency: string, locale: Locale): string | null {
  if (price === null) return null;
  const amount = Number(price);
  return new Intl.NumberFormat(INTL_LOCALE[locale], {
    style: "currency",
    currency,
    minimumFractionDigits: Number.isInteger(amount) ? 0 : 2,
  }).format(amount);
}

/** The calendar date (YYYY-MM-DD) in the clinic's time zone, `offsetDays` from `now`. */
export function clinicDate(timeZone: string, offsetDays = 0, now: Date = new Date()): string {
  const shifted = new Date(now.getTime() + offsetDays * 86_400_000);
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" })
    .formatToParts(shifted)
    .reduce<Record<string, string>>((acc, part) => ({ ...acc, [part.type]: part.value }), {});
  return `${parts.year}-${parts.month}-${parts.day}`;
}

/** Monday = 0 … Sunday = 6 for "now" in the clinic's time zone. */
export function clinicWeekday(timeZone: string, now: Date = new Date()): number {
  const day = new Date(`${clinicDate(timeZone, 0, now)}T12:00:00Z`).getUTCDay();
  return (day + 6) % 7;
}

/** Initials for a monogram: "Dr. Arta Krasniqi" -> "AK". */
export function initials(name: string): string {
  const words = name.replace(/^(dr\.?|doc\.?)\s+/i, "").split(/\s+/).filter(Boolean);
  return words.length ? (words[0][0] + (words.length > 1 ? words[words.length - 1][0] : "")).toUpperCase() : "";
}

export function interpolate(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}
