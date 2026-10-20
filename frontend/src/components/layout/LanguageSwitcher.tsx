"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { LANGUAGE_NAMES, LOCALES, type Locale } from "@/lib/locale";

/** Links to the same page in the other languages. */
export function LanguageSwitcher({ locale, label }: { locale: Locale; label: string }) {
  const pathname = usePathname();
  const rest = pathname.split("/").slice(2).join("/");
  return (
    <nav aria-label={label}>
      <ul className="flex items-center gap-1 text-xs tracking-wider uppercase">
        {LOCALES.map((code) => (
          <li key={code}>
            <Link
              href={`/${code}${rest ? `/${rest}` : ""}`}
              hrefLang={code}
              lang={code}
              aria-current={code === locale ? "true" : undefined}
              title={LANGUAGE_NAMES[code]}
              className={`inline-flex min-h-9 min-w-9 items-center justify-center rounded-full px-2 transition-colors ${
                code === locale ? "bg-sand text-forest" : "text-muted hover:text-forest"
              }`}
            >
              <span className="sr-only">{LANGUAGE_NAMES[code]}</span>
              <span aria-hidden="true">{code}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
