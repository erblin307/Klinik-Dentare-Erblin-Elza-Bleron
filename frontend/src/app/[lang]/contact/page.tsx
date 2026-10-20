import { OpeningHours } from "@/components/content/OpeningHours";
import { OpenChatButton } from "@/components/chat/OpenChatButton";
import { ButtonLink } from "@/components/ui/ButtonLink";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { Notice } from "@/components/ui/Notice";
import { PageHeader } from "@/components/ui/PageHeader";
import { getClinic } from "@/lib/api";
import { clinicWeekday, formatDate } from "@/lib/format";
import { localeFrom, unavailableText } from "@/lib/page";
import { clinicJsonLd, jsonLdScript, pageMetadata, siteDescription } from "@/lib/seo";

export async function generateMetadata({ params }: PageProps<"/[lang]/contact">) {
  const { lang, t } = await localeFrom(params);
  return pageMetadata(lang, "contact", t.contact.title, siteDescription(t, await getClinic()));
}

export default async function ContactPage({ params }: PageProps<"/[lang]/contact">) {
  const { lang, t } = await localeFrom(params);
  const clinic = await getClinic();
  if (!clinic) {
    return (
      <>
        <PageHeader eyebrow={t.nav.contact} title={t.contact.title} />
        <Container>
          <Notice>{unavailableText(t)}</Notice>
        </Container>
      </>
    );
  }
  const addressLines = [clinic.address_line, [clinic.postal_code, clinic.city].filter(Boolean).join(" "), clinic.country].filter(Boolean);
  const mapUrl = `https://www.openstreetmap.org/search?query=${encodeURIComponent(addressLines.join(", "))}`;

  return (
    <>
      <PageHeader eyebrow={t.nav.contact} title={t.contact.title} lead={t.contact.lead} />
      <Container className="grid gap-16 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <dl className="divide-y divide-line border-y border-line">
            {addressLines.length > 0 && (
              <div className="grid gap-2 py-6 sm:grid-cols-3">
                <dt className="flex items-center gap-2 text-sm text-muted">
                  <Icon name="pin" className="h-4 w-4" />
                  {t.contact.address}
                </dt>
                <dd className="sm:col-span-2">
                  <address className="font-display text-2xl leading-snug not-italic">
                    {addressLines.map((line) => (
                      <span key={line} className="block">
                        {line}
                      </span>
                    ))}
                  </address>
                  <a href={mapUrl} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block text-sm text-forest underline underline-offset-4">
                    {t.contact.mapNote}
                  </a>
                </dd>
              </div>
            )}
            {clinic.phone && (
              <div className="grid gap-2 py-6 sm:grid-cols-3">
                <dt className="flex items-center gap-2 text-sm text-muted">
                  <Icon name="phone" className="h-4 w-4" />
                  {t.contact.phone}
                </dt>
                <dd className="font-display text-2xl sm:col-span-2">
                  <a href={`tel:${clinic.phone.replace(/\s/g, "")}`} className="hover:text-forest">
                    {clinic.phone}
                  </a>
                </dd>
              </div>
            )}
            {clinic.email && (
              <div className="grid gap-2 py-6 sm:grid-cols-3">
                <dt className="flex items-center gap-2 text-sm text-muted">
                  <Icon name="mail" className="h-4 w-4" />
                  {t.contact.email}
                </dt>
                <dd className="font-display text-2xl break-all sm:col-span-2">
                  <a href={`mailto:${clinic.email}`} className="hover:text-forest">
                    {clinic.email}
                  </a>
                </dd>
              </div>
            )}
          </dl>
          <div className="mt-10 flex flex-wrap gap-3">
            <ButtonLink href={`/${lang}/book`}>{t.nav.book}</ButtonLink>
            <OpenChatButton label={t.contact.askAssistant} />
          </div>
        </div>
        <aside className="lg:col-span-5">
          <div className="rounded-2xl border border-line bg-paper p-6 md:p-8">
            <h2 className="flex items-center gap-2 font-sans text-xs font-medium tracking-[0.18em] text-brass uppercase">
              <Icon name="clock" className="h-4 w-4" />
              {t.contact.hours}
            </h2>
            <div className="mt-3">
              <OpeningHours
                hours={clinic.opening_hours}
                locale={lang}
                closedLabel={t.contact.closed}
                highlightToday={clinicWeekday(clinic.timezone)}
              />
            </div>
            <p className="mt-3 text-xs text-muted">{t.contact.hoursNote}</p>
            {clinic.closures.length > 0 && (
              <div className="mt-8">
                <h3 className="font-sans text-xs font-medium tracking-[0.18em] text-muted uppercase">{t.contact.closures}</h3>
                <ul className="mt-3 space-y-1.5 text-sm">
                  {clinic.closures.map((closure) => (
                    <li key={closure.start}>
                      {formatDate(closure.start, lang, clinic.timezone, "short")}
                      {closure.end.slice(0, 10) !== closure.start.slice(0, 10) &&
                        ` – ${formatDate(new Date(new Date(closure.end).getTime() - 1).toISOString(), lang, clinic.timezone, "short")}`}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </aside>
      </Container>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(clinicJsonLd(clinic, lang)) }} />
    </>
  );
}
