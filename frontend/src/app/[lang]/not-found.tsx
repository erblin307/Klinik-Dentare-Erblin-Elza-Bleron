"use client";

import { usePathname } from "next/navigation";

import { ButtonLink } from "@/components/ui/ButtonLink";
import { Container } from "@/components/ui/Container";
import { getDictionary } from "@/dictionaries";
import { DEFAULT_LOCALE, isLocale } from "@/lib/locale";

export default function NotFound() {
  const segment = usePathname().split("/")[1] ?? "";
  const locale = isLocale(segment) ? segment : DEFAULT_LOCALE;
  const t = getDictionary(locale).common;
  return (
    <Container className="py-28 md:py-40">
      <p className="text-xs font-medium tracking-[0.18em] text-brass uppercase">404</p>
      <h1 className="mt-5 text-5xl md:text-7xl">{t.notFoundTitle}</h1>
      <p className="mt-6 max-w-xl text-lg text-muted">{t.notFoundBody}</p>
      <ButtonLink href={`/${locale}`} className="mt-10">
        {t.backHome}
      </ButtonLink>
    </Container>
  );
}
