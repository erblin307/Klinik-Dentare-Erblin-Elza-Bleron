import Link from "next/link";

import type { Dictionary } from "@/dictionaries";
import { initials, interpolate } from "@/lib/format";
import type { Locale } from "@/lib/locale";
import type { Dentist, Service } from "@/lib/types";

import { OpeningHours } from "./OpeningHours";

type Props = {
  dentist: Dentist;
  locale: Locale;
  t: Dictionary["dentists"];
  closedLabel: string;
  services?: Service[] | null;
  compact?: boolean;
};

/** A dentist with a monogram (there is no photo field; no stand-in faces are used). */
export function DentistProfile({ dentist, locale, t, closedLabel, services, compact = false }: Props) {
  const treatments = (services ?? []).filter((s) => dentist.service_ids.includes(s.id));
  return (
    <article className="flex flex-col">
      <div
        aria-hidden="true"
        className="flex aspect-[5/4] items-center justify-center sm:aspect-[4/5] rounded-t-[999px] bg-sage font-display text-6xl text-forest md:text-7xl"
      >
        {initials(dentist.name)}
      </div>
      <h3 className="mt-6 text-3xl leading-tight">{dentist.name}</h3>
      {dentist.specialty && <p className="mt-1 text-sm tracking-wide text-brass">{dentist.specialty}</p>}
      {!compact && dentist.bio && <p className="mt-4 leading-relaxed text-muted">{dentist.bio}</p>}
      {!compact && treatments.length > 0 && (
        <div className="mt-6">
          <h4 className="text-xs font-medium tracking-[0.18em] text-muted uppercase">{t.services}</h4>
          <p className="mt-2 text-sm leading-relaxed">{treatments.map((s) => s.name).join(" · ")}</p>
        </div>
      )}
      {!compact && (
        <div className="mt-6">
          <h4 className="mb-1 text-xs font-medium tracking-[0.18em] text-muted uppercase">{t.hours}</h4>
          {dentist.working_hours.length ? (
            <OpeningHours hours={dentist.working_hours} locale={locale} closedLabel={closedLabel} />
          ) : (
            <p className="text-sm text-muted">{t.noHours}</p>
          )}
        </div>
      )}
      {!compact && dentist.service_ids.length > 0 && (
        <Link
          href={`/${locale}/book?dentist=${dentist.id}`}
          className="mt-6 text-sm font-medium text-forest underline decoration-forest/30 underline-offset-[6px] hover:decoration-forest"
        >
          {interpolate(t.book, { name: dentist.name })}
        </Link>
      )}
    </article>
  );
}
