import { Container } from "@/components/ui/Container";
import { Notice } from "@/components/ui/Notice";
import { PageHeader } from "@/components/ui/PageHeader";
import { PhotoSlot } from "@/components/ui/PhotoSlot";
import { getArticles, getClinic, getDentists, getServices } from "@/lib/api";
import { localeFrom, unavailableText } from "@/lib/page";
import { pageMetadata, siteDescription } from "@/lib/seo";

export async function generateMetadata({ params }: PageProps<"/[lang]/about">) {
  const { lang, t } = await localeFrom(params);
  return pageMetadata(lang, "about", t.about.title, siteDescription(t, await getClinic()));
}

export default async function AboutPage({ params }: PageProps<"/[lang]/about">) {
  const { lang, t } = await localeFrom(params);
  const [clinic, articles, catalog, dentists] = await Promise.all([
    getClinic(),
    getArticles(lang, "general"),
    getServices(),
    getDentists(),
  ]);
  const facts = [
    catalog && { value: catalog.services.length, label: t.about.servicesCount },
    dentists && { value: dentists.length, label: t.about.dentistsCount },
    clinic && { value: new Set(clinic.opening_hours.map((h) => h.weekday)).size, label: t.about.daysOpen },
  ].filter((fact): fact is { value: number; label: string } => Boolean(fact));

  return (
    <>
      <PageHeader eyebrow={t.nav.about} title={t.about.title} lead={t.about.lead} />
      <Container className="grid gap-14 lg:grid-cols-12">
        <div className="space-y-14 lg:col-span-7">
          {articles === null && <Notice>{unavailableText(t)}</Notice>}
          {articles?.length === 0 && (
            <Notice tone="demo">
              <strong className="font-medium">{t.about.placeholderTitle}.</strong> {t.about.placeholderBody}
            </Notice>
          )}
          {articles?.map((article) => (
            <article key={article.id} lang={article.language}>
              <h2 className="text-4xl leading-tight">{article.title}</h2>
              <p className="prose-clinic mt-5 text-lg text-muted">{article.content}</p>
            </article>
          ))}
        </div>
        <aside className="lg:col-span-5">
          <PhotoSlot
            slot="reception"
            alt={t.common.photoAlt.reception}
            placeholderLabel={t.common.demoPhoto}
            demoLabel={t.common.demoPhotoBadge}
            className="aspect-[4/3] rounded-sm"
            sizes="(min-width: 1024px) 40vw, 100vw"
          />
          {facts.length > 0 && (
            <div className="mt-10">
              <h2 className="font-sans text-xs font-medium tracking-[0.18em] text-brass uppercase">{t.about.facts}</h2>
              <dl className="mt-4 grid grid-cols-3 divide-x divide-line border-y border-line">
                {facts.map((fact) => (
                  <div key={fact.label} className="px-4 py-6 first:pl-0">
                    <dt className="sr-only">{fact.label}</dt>
                    <dd>
                      <span className="block font-display text-5xl text-forest lining-nums tabular-nums">{fact.value}</span>
                      <span className="mt-1 block text-xs text-muted">{fact.label}</span>
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </aside>
      </Container>
    </>
  );
}
