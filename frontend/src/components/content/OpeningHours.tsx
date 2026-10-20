import { weekdayName } from "@/lib/format";
import type { Locale } from "@/lib/locale";
import type { Hours } from "@/lib/types";

/** Monday–Sunday with all blocks of each day; days without blocks show `closedLabel`. */
export function OpeningHours({
  hours,
  locale,
  closedLabel,
  highlightToday,
}: {
  hours: Hours[];
  locale: Locale;
  closedLabel: string;
  highlightToday?: number;
}) {
  const days = Array.from({ length: 7 }, (_, weekday) => ({
    weekday,
    blocks: hours.filter((h) => h.weekday === weekday),
  }));
  return (
    <dl className="divide-y divide-line text-sm">
      {days.map(({ weekday, blocks }) => (
        <div
          key={weekday}
          className={`flex justify-between gap-6 py-2.5 ${weekday === highlightToday ? "font-medium text-ink" : "text-muted"}`}
        >
          {/* First letter only: Albanian "e hënë" must not become "E Hënë". */}
          <dt className="first-letter:uppercase">{weekdayName(weekday, locale)}</dt>
          <dd className="text-right tabular-nums">
            {blocks.length ? blocks.map((b) => `${b.start}–${b.end}`).join(", ") : closedLabel}
          </dd>
        </div>
      ))}
    </dl>
  );
}
