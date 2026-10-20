import Link from "next/link";

import type { Dictionary } from "@/dictionaries";
import { formatPrice, interpolate } from "@/lib/format";
import type { Locale } from "@/lib/locale";
import type { Dentist, Service } from "@/lib/types";

type Props = {
  services: Service[];
  currency: string;
  locale: Locale;
  t: Dictionary["services"];
  dentists?: Dentist[] | null;
  detailed?: boolean;
};

/** Services as a price list: name, duration, price, booking link. */
export function ServiceRows({ services, currency, locale, t, dentists, detailed = false }: Props) {
  if (!services.length) return <p className="text-muted">{t.empty}</p>;
  const names = new Map((dentists ?? []).map((d) => [d.id, d.name]));
  return (
    <ul className="divide-y divide-line border-y border-line">
      {services.map((service) => {
        const price = formatPrice(service.price, currency, locale);
        const performers = service.dentist_ids.map((id) => names.get(id)).filter(Boolean);
        const bookable = service.dentist_ids.length > 0;
        return (
          <li key={service.id} className="grid gap-3 py-6 md:grid-cols-12 md:items-baseline md:gap-8">
            <div className="md:col-span-6">
              <h3 className="text-2xl leading-tight md:text-[1.7rem]">{service.name}</h3>
              {detailed && service.description && (
                <p className="mt-2 max-w-xl leading-relaxed text-muted">{service.description}</p>
              )}
              {detailed && performers.length > 0 && (
                <p className="mt-2 text-sm text-muted">{interpolate(t.performedBy, { names: performers.join(", ") })}</p>
              )}
            </div>
            <p className="text-sm text-muted tabular-nums md:col-span-2">
              {interpolate(t.duration, { minutes: service.duration_minutes })}
            </p>
            <p className="font-medium tabular-nums md:col-span-2 md:text-right">
              {price ?? <span className="text-sm font-normal text-muted">{t.priceOnConsultation}</span>}
            </p>
            <div className="md:col-span-2 md:text-right">
              {bookable && (
                <Link
                  href={`/${locale}/book?service=${service.id}`}
                  className="text-sm font-medium text-forest underline decoration-forest/30 underline-offset-[6px] hover:decoration-forest"
                  aria-label={`${t.book}: ${service.name}`}
                >
                  {t.book}
                </Link>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
