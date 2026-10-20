import Image from "next/image";
import Link from "next/link";

import type { Dictionary } from "@/dictionaries";
import { initials, interpolate } from "@/lib/format";
import type { Locale } from "@/lib/locale";
import { isDemoPhoto } from "@/lib/photos";
import type { Dentist, Service } from "@/lib/types";

import { OpeningHours } from "./OpeningHours";

type Props = {
  dentist: Dentist;
  locale: Locale;
  t: Dictionary["dentists"];
  closedLabel: string;
  demoPhotoLabel: string;
  services?: Service[] | null;
  compact?: boolean;
};

/** A dentist with their portrait in an arch, or a monogram when there is no photo. */
export function DentistProfile({ dentist, locale, t, closedLabel, demoPhotoLabel, services, compact = false }: Props) {
  const treatments = (services ?? []).filter((s) => dentist.service_ids.includes(s.id));
  return (
    <article className="flex flex-col">
      {dentist.photo ? (
        <div className="relative aspect-[4/5] overflow-hidden rounded-t-[999px] bg-sage">
          <Image
            src={dentist.photo}
            alt={dentist.name}
            fill
            sizes="(min-width: 1024px) 360px, (min-width: 640px) 45vw, 100vw"
            className="object-cover"
          />
          {isDemoPhoto(dentist.photo) && (
            <span className="absolute bottom-3 left-3 rounded-full bg-ivory/90 px-3 py-1 text-[11px] font-medium tracking-wide text-ink">
              {demoPhotoLabel}
            </span>
          )}
        </div>
      ) : (
        <div
          aria-hidden="true"
          className="flex aspect-[5/4] items-center justify-center rounded-t-[999px] bg-sage font-display text-6xl text-forest sm:aspect-[4/5] md:text-7xl"
        >
          {initials(dentist.name)}
        </div>
      )}
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
