import { ServiceRows } from "@/components/content/ServiceRows";
import { Container } from "@/components/ui/Container";
import { Notice } from "@/components/ui/Notice";
import { PageHeader } from "@/components/ui/PageHeader";
import { getClinic, getDentists, getServices } from "@/lib/api";
import { interpolate } from "@/lib/format";
import { localeFrom, unavailableText } from "@/lib/page";
import { pageMetadata, siteDescription } from "@/lib/seo";

export async function generateMetadata({ params }: PageProps<"/[lang]/services">) {
  const { lang, t } = await localeFrom(params);
  return pageMetadata(lang, "services", t.services.title, siteDescription(t, await getClinic()));
}

export default async function ServicesPage({ params }: PageProps<"/[lang]/services">) {
  const { lang, t } = await localeFrom(params);
  const [catalog, dentists] = await Promise.all([getServices(), getDentists()]);
  return (
    <>
      <PageHeader
        eyebrow={t.nav.services}
        title={t.services.title}
        lead={catalog ? interpolate(t.services.lead, { currency: catalog.currency }) : undefined}
      />
      <Container>
        {catalog ? (
          <ServiceRows
            services={catalog.services}
            currency={catalog.currency}
            locale={lang}
            t={t.services}
            dentists={dentists}
            detailed
          />
        ) : (
          <Notice>{unavailableText(t)}</Notice>
        )}
      </Container>
    </>
  );
}
