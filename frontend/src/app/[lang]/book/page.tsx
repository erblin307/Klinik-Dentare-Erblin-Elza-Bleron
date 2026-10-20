import { BookingPlanner } from "@/components/booking/BookingPlanner";
import { Container } from "@/components/ui/Container";
import { Notice } from "@/components/ui/Notice";
import { PageHeader } from "@/components/ui/PageHeader";
import { clinicSlug, getClinic, getDentists, getServices } from "@/lib/api";
import { localeFrom, unavailableText } from "@/lib/page";
import { pageMetadata, siteDescription } from "@/lib/seo";

export async function generateMetadata({ params }: PageProps<"/[lang]/book">) {
  const { lang, t } = await localeFrom(params);
  return pageMetadata(lang, "book", t.book.title, siteDescription(t, await getClinic()));
}

function idParam(value: string | string[] | undefined): number | null {
  const number = Number(Array.isArray(value) ? value[0] : value);
  return Number.isInteger(number) && number > 0 ? number : null;
}

export default async function BookPage({ params, searchParams }: PageProps<"/[lang]/book">) {
  const { lang, t } = await localeFrom(params);
  const query = await searchParams;
  const [clinic, catalog, dentists] = await Promise.all([getClinic(), getServices(), getDentists()]);
  const slug = clinicSlug();

  return (
    <>
      <PageHeader eyebrow={t.nav.book} title={t.book.title} lead={t.book.lead} />
      <Container>
        {clinic && catalog && dentists && slug ? (
          <BookingPlanner
            clinicSlug={slug}
            timezone={clinic.timezone}
            phone={clinic.phone}
            locale={lang}
            services={catalog.services}
            dentists={dentists}
            initialServiceId={idParam(query.service)}
            initialDentistId={idParam(query.dentist)}
            t={t.book}
            handoffTemplate={t.chat.handoff}
          />
        ) : (
          <Notice>{unavailableText(t)}</Notice>
        )}
      </Container>
    </>
  );
}
