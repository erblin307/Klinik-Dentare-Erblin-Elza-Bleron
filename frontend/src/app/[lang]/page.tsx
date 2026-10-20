import { ArticleAccordion } from "@/components/content/ArticleList";
import { DentistProfile } from "@/components/content/DentistProfile";
import { ServiceRows } from "@/components/content/ServiceRows";
import { ArrowLink, ButtonLink } from "@/components/ui/ButtonLink";
import { Container } from "@/components/ui/Container";
import { Notice } from "@/components/ui/Notice";
import { PhotoSlot } from "@/components/ui/PhotoSlot";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { getArticles, getClinic, getDentists, getServices } from "@/lib/api";
import { clinicWeekday, interpolate } from "@/lib/format";
import { localeFrom, unavailableText } from "@/lib/page";
import { clinicJsonLd, jsonLdScript, pageMetadata, siteDescription } from "@/lib/seo";

export async function generateMetadata({ params }: PageProps<"/[lang]">) {
  const { lang, t } = await localeFrom(params);
  return pageMetadata(lang, "", null, siteDescription(t, await getClinic()));
}

export default async function HomePage({ params }: PageProps<"/[lang]">) {
  const { lang, t } = await localeFrom(params);
  const [clinic, catalog, dentists, faq] = await Promise.all([
    getClinic(),
    getServices(),
    getDentists(),
    getArticles(lang, "faq"),
  ]);
  const inCity = clinic?.city ? interpolate(t.meta.inCity, { city: clinic.city }) : "";
  const today = clinic && clinic.opening_hours.find((h) => h.weekday === clinicWeekday(clinic.timezone));
  const address = clinic && [clinic.address_line, clinic.city].filter(Boolean).join(", ");

  return (
    <>
      <section className="pt-10 pb-16 md:pt-16 md:pb-24">
        <Container className="grid items-end gap-12 md:grid-cols-12">
          <div className="md:col-span-7 md:pb-8">
            <p className="text-xs font-medium tracking-[0.18em] text-brass uppercase">
              {interpolate(t.home.eyebrow, { inCity })}
            </p>
            <h1 className="mt-6 text-[3.1rem] leading-[0.98] sm:text-6xl lg:text-[5.4rem]">{t.home.title}</h1>
            <p className="mt-8 max-w-xl text-lg leading-relaxed text-muted md:text-xl">{t.home.lead}</p>
            <div className="mt-10 flex flex-wrap gap-3">
              <ButtonLink href={`/${lang}/book`}>{t.home.ctaBook}</ButtonLink>
              <ButtonLink href={`/${lang}/services`} variant="secondary">
                {t.home.ctaServices}
              </ButtonLink>
            </div>
            {clinic && (
              <dl className="mt-14 grid gap-6 border-t border-line pt-6 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-xs tracking-[0.14em] text-muted uppercase">{t.contact.hours}</dt>
                  <dd className="mt-1.5">
                    {today ? interpolate(t.home.todayOpen, { hours: `${today.start}–${today.end}` }) : t.home.todayClosed}
                  </dd>
                </div>
                {clinic.phone && (
                  <div>
                    <dt className="text-xs tracking-[0.14em] text-muted uppercase">{t.contact.phone}</dt>
                    <dd className="mt-1.5">
                      <a href={`tel:${clinic.phone.replace(/\s/g, "")}`} className="hover:text-forest">
                        {clinic.phone}
                      </a>
                    </dd>
                  </div>
                )}
                {address && (
                  <div>
                    <dt className="text-xs tracking-[0.14em] text-muted uppercase">{t.contact.address}</dt>
                    <dd className="mt-1.5">{address}</dd>
                  </div>
                )}
              </dl>
            )}
          </div>
          <div className="md:col-span-5">
            <PhotoSlot
              slot="hero"
              alt={t.common.photoAlt.hero}
              placeholderLabel={t.common.demoPhoto}
              demoLabel={t.common.demoPhotoBadge}
              className="aspect-[4/5] rounded-t-[999px]"
              sizes="(min-width: 768px) 40vw, 100vw"
              priority
            />
          </div>
        </Container>
      </section>

      <section aria-labelledby="services-title" className="py-16 md:py-24">
        <Container>
          <SectionHeading
            id="services-title"
            index="01"
            eyebrow={t.home.servicesEyebrow}
            title={t.home.servicesTitle}
            lead={t.home.servicesLead}
          />
          {catalog ? (
            <>
              <ServiceRows services={catalog.services.slice(0, 6)} currency={catalog.currency} locale={lang} t={t.services} />
              <ArrowLink href={`/${lang}/services`} className="mt-8">
                {t.home.allServices}
              </ArrowLink>
            </>
          ) : (
            <Notice>{unavailableText(t)}</Notice>
          )}
        </Container>
      </section>

      <Container>
        <PhotoSlot
          slot="treatment"
          alt={t.common.photoAlt.treatment}
          placeholderLabel={t.common.demoPhoto}
          demoLabel={t.common.demoPhotoBadge}
          className="aspect-[16/9] rounded-sm md:aspect-[21/9]"
          sizes="(min-width: 1152px) 1152px, 100vw"
        />
      </Container>

      <section aria-labelledby="team-title" className="py-16 md:py-24">
        <Container>
          <SectionHeading
            id="team-title"
            index="02"
            eyebrow={t.home.teamEyebrow}
            title={t.home.teamTitle}
            action={dentists?.length ? <ArrowLink href={`/${lang}/dentists`}>{t.home.allDentists}</ArrowLink> : undefined}
          />
          {dentists === null ? (
            <Notice>{unavailableText(t)}</Notice>
          ) : dentists.length ? (
            <div className="grid gap-x-10 gap-y-14 sm:grid-cols-2 lg:grid-cols-3">
              {dentists.slice(0, 3).map((dentist) => (
                <DentistProfile key={dentist.id} dentist={dentist} locale={lang} t={t.dentists} closedLabel={t.contact.closed} compact />
              ))}
            </div>
          ) : (
            <p className="text-muted">{t.dentists.empty}</p>
          )}
        </Container>
      </section>

      {faq && faq.length > 0 && (
        <section aria-labelledby="faq-title" className="py-16 md:py-24">
          <Container>
            <SectionHeading
              id="faq-title"
              index="03"
              eyebrow={t.home.faqEyebrow}
              title={t.home.faqTitle}
              action={<ArrowLink href={`/${lang}/faq`}>{t.home.allFaq}</ArrowLink>}
            />
            <div className="md:ml-[25%]">
              <ArticleAccordion articles={faq.slice(0, 4)} />
            </div>
          </Container>
        </section>
      )}

      <section className="bg-forest text-ivory">
        <Container className="grid gap-10 py-20 md:grid-cols-12 md:items-end md:py-28">
          <h2 className="text-4xl leading-[1.02] text-ivory md:col-span-7 md:text-6xl">{t.home.bandTitle}</h2>
          <div className="md:col-span-5">
            <p className="leading-relaxed text-ivory/80">{t.home.bandLead}</p>
            <ButtonLink href={`/${lang}/book`} variant="light" className="mt-8">
              {t.home.ctaBook}
            </ButtonLink>
          </div>
        </Container>
      </section>

      {clinic && (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(clinicJsonLd(clinic, lang)) }} />
      )}
    </>
  );
}
