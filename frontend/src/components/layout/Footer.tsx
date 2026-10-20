import Link from "next/link";

import { OpeningHours } from "@/components/content/OpeningHours";
import { Container } from "@/components/ui/Container";
import type { Dictionary } from "@/dictionaries";
import type { Locale } from "@/lib/locale";
import { href, navItems } from "@/lib/navigation";
import type { Clinic } from "@/lib/types";

export function Footer({ locale, t, clinic }: { locale: Locale; t: Dictionary; clinic: Clinic | null }) {
  const address = clinic ? [clinic.address_line, [clinic.postal_code, clinic.city].filter(Boolean).join(" ")].filter(Boolean) : [];
  return (
    <footer className="mt-24 bg-sand">
      <Container className="grid gap-12 py-16 md:grid-cols-12 md:py-20">
        <div className="md:col-span-4">
          <p className="font-display text-3xl text-forest">{clinic?.name ?? t.meta.dentalClinic}</p>
          {address.length > 0 && (
            <address className="mt-4 text-sm leading-relaxed text-muted not-italic">
              {address.map((line) => (
                <span key={line} className="block">
                  {line}
                </span>
              ))}
            </address>
          )}
        </div>
        <div className="text-sm md:col-span-3">
          <h2 className="font-sans text-xs font-medium tracking-[0.18em] text-brass uppercase">{t.nav.contact}</h2>
          <ul className="mt-4 space-y-2">
            {clinic?.phone && (
              <li>
                <a href={`tel:${clinic.phone.replace(/\s/g, "")}`} className="hover:text-forest">
                  {clinic.phone}
                </a>
              </li>
            )}
            {clinic?.email && (
              <li>
                <a href={`mailto:${clinic.email}`} className="hover:text-forest">
                  {clinic.email}
                </a>
              </li>
            )}
            <li>
              <Link href={`/${locale}/book`} className="text-forest underline decoration-forest/30 underline-offset-4">
                {t.nav.book}
              </Link>
            </li>
          </ul>
        </div>
        <div className="md:col-span-3">
          <h2 className="font-sans text-xs font-medium tracking-[0.18em] text-brass uppercase">{t.contact.hours}</h2>
          <div className="mt-2">
            {clinic ? (
              <OpeningHours hours={clinic.opening_hours} locale={locale} closedLabel={t.contact.closed} />
            ) : (
              <p className="mt-2 text-sm text-muted">{t.common.unavailable}</p>
            )}
          </div>
        </div>
        <div className="text-sm md:col-span-2">
          <ul className="space-y-2">
            {navItems(t.nav).map((item) => (
              <li key={item.path}>
                <Link href={href(locale, item.path)} className="text-muted hover:text-forest">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </Container>
      <div className="border-t border-line">
        <Container className="flex flex-col gap-3 py-6 text-xs text-muted md:flex-row md:items-center md:justify-between">
          <p>
            © {new Date().getFullYear()} {clinic?.name ?? t.meta.dentalClinic}. {t.common.rights}
          </p>
          <p className="max-w-xl md:text-right">
            <span className="mr-2 rounded-full bg-ivory px-2 py-0.5 font-medium tracking-wider text-brass uppercase">Demo</span>
            {t.common.demoNotice}
          </p>
        </Container>
      </div>
    </footer>
  );
}
