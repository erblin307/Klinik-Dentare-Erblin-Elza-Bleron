import { DentistProfile } from "@/components/content/DentistProfile";
import { Container } from "@/components/ui/Container";
import { Notice } from "@/components/ui/Notice";
import { PageHeader } from "@/components/ui/PageHeader";
import { getClinic, getDentists, getServices } from "@/lib/api";
import { localeFrom, unavailableText } from "@/lib/page";
import { pageMetadata, siteDescription } from "@/lib/seo";

export async function generateMetadata({ params }: PageProps<"/[lang]/dentists">) {
  const { lang, t } = await localeFrom(params);
  return pageMetadata(lang, "dentists", t.dentists.title, siteDescription(t, await getClinic()));
}

export default async function DentistsPage({ params }: PageProps<"/[lang]/dentists">) {
  const { lang, t } = await localeFrom(params);
  const [dentists, catalog] = await Promise.all([getDentists(), getServices()]);
  return (
    <>
      <PageHeader eyebrow={t.nav.dentists} title={t.dentists.title} lead={t.dentists.lead} />
      <Container>
        {dentists === null ? (
          <Notice>{unavailableText(t)}</Notice>
        ) : dentists.length ? (
          <div className="grid gap-x-12 gap-y-20 sm:grid-cols-2 lg:grid-cols-3">
            {dentists.map((dentist) => (
              <DentistProfile
                key={dentist.id}
                dentist={dentist}
                locale={lang}
                t={t.dentists}
                closedLabel={t.contact.closed}
                services={catalog?.services}
              />
            ))}
          </div>
        ) : (
          <p className="text-muted">{t.dentists.empty}</p>
        )}
      </Container>
    </>
  );
}
