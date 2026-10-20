import { ArticleAccordion } from "@/components/content/ArticleList";
import { OpenChatButton } from "@/components/chat/OpenChatButton";
import { Container } from "@/components/ui/Container";
import { Notice } from "@/components/ui/Notice";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { getArticles, getClinic } from "@/lib/api";
import { localeFrom, unavailableText } from "@/lib/page";
import { pageMetadata, siteDescription } from "@/lib/seo";

export async function generateMetadata({ params }: PageProps<"/[lang]/faq">) {
  const { lang, t } = await localeFrom(params);
  return pageMetadata(lang, "faq", t.faq.title, siteDescription(t, await getClinic()));
}

export default async function FaqPage({ params }: PageProps<"/[lang]/faq">) {
  const { lang, t } = await localeFrom(params);
  const [faq, policies, pricing, clinic] = await Promise.all([
    getArticles(lang, "faq"),
    getArticles(lang, "policies"),
    getArticles(lang, "pricing"),
    getClinic(),
  ]);
  const questions = [...(faq ?? []), ...(pricing ?? [])];
  const all = [...questions, ...(policies ?? [])];
  const otherLanguage = all.some((article) => article.language !== lang);

  return (
    <>
      <PageHeader eyebrow={t.nav.faq} title={t.faq.title} lead={t.faq.lead} />
      <Container className="space-y-20">
        {faq === null ? (
          <Notice>{unavailableText(t)}</Notice>
        ) : all.length === 0 ? (
          <p className="text-muted">{t.faq.empty}</p>
        ) : (
          <>
            {otherLanguage && <Notice>{t.faq.otherLanguage}</Notice>}
            {questions.length > 0 && <ArticleAccordion articles={questions} />}
            {policies && policies.length > 0 && (
              <section aria-labelledby="policies-title">
                <SectionHeading id="policies-title" eyebrow={t.nav.faq} title={t.faq.policies} />
                <ArticleAccordion articles={policies} />
              </section>
            )}
          </>
        )}
        <div className="flex flex-col gap-6 border-t border-line pt-10 md:flex-row md:items-center md:justify-between">
          <p className="font-display text-3xl">{t.faq.stillQuestions}</p>
          <div className="flex flex-wrap gap-3">
            <OpenChatButton label={t.contact.askAssistant} variant="primary" />
            {clinic?.phone && (
              <a href={`tel:${clinic.phone.replace(/\s/g, "")}`} className="inline-flex min-h-11 items-center rounded-full border border-forest/25 px-6 text-sm font-medium text-forest">
                {clinic.phone}
              </a>
            )}
          </div>
        </div>
      </Container>
    </>
  );
}
