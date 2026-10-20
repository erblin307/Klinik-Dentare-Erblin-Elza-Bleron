import Link from "next/link";

import { ButtonLink } from "@/components/ui/ButtonLink";
import { Container } from "@/components/ui/Container";
import type { Dictionary } from "@/dictionaries";
import type { Locale } from "@/lib/locale";
import { navItems } from "@/lib/navigation";
import type { Clinic } from "@/lib/types";

import { LanguageSwitcher } from "./LanguageSwitcher";
import { MobileNav } from "./MobileNav";
import { NavLinks } from "./NavLinks";

export function Header({ locale, t, clinic }: { locale: Locale; t: Dictionary; clinic: Clinic | null }) {
  const items = navItems(t.nav);
  return (
    <header className="sticky top-0 z-40 border-b border-line/80 bg-ivory/95 backdrop-blur supports-[backdrop-filter]:bg-ivory/85">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:rounded-full focus:bg-forest focus:px-4 focus:py-2 focus:text-ivory"
      >
        {t.nav.skipToContent}
      </a>
      <Container className="flex h-[72px] items-center justify-between gap-6">
        <Link href={`/${locale}`} className="flex flex-col leading-none">
          <span className="font-display text-2xl text-forest">{clinic?.name ?? t.meta.dentalClinic}</span>
          {clinic && (
            <span className="mt-1 text-[10px] tracking-[0.22em] text-brass uppercase">{t.meta.dentalClinic}</span>
          )}
        </Link>
        <nav aria-label={t.nav.primary} className="hidden lg:block">
          <NavLinks locale={locale} items={items} orientation="horizontal" />
        </nav>
        <div className="flex items-center gap-3">
          <div className="hidden lg:block">
            <LanguageSwitcher locale={locale} label={t.nav.language} />
          </div>
          {/* Visibility on a wrapper: the button's own inline-flex would override "hidden". */}
          <div className="hidden sm:block">
            <ButtonLink href={`/${locale}/book`}>{t.nav.book}</ButtonLink>
          </div>
          <MobileNav
            locale={locale}
            items={items}
            labels={{
              open: t.nav.openMenu,
              close: t.nav.closeMenu,
              book: t.nav.book,
              language: t.nav.language,
              primary: t.nav.primary,
            }}
          />
        </div>
      </Container>
    </header>
  );
}
