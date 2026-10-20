import type { Metadata } from "next";

import type { Dictionary } from "@/dictionaries";

import { interpolate } from "./format";
import { DEFAULT_LOCALE, LOCALES, type Locale } from "./locale";
import type { Clinic } from "./types";

export function siteUrl(): string {
  return (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/$/, "");
}

/** Title, description, canonical URL and hreflang alternates for a page. */
export function pageMetadata(locale: Locale, path: string, title: string | null, description: string): Metadata {
  const suffix = path ? `/${path}` : "";
  const languages = Object.fromEntries(LOCALES.map((code) => [code, `/${code}${suffix}`]));
  return {
    ...(title ? { title } : {}),
    description,
    alternates: {
      canonical: `/${locale}${suffix}`,
      languages: { ...languages, "x-default": `/${DEFAULT_LOCALE}${suffix}` },
    },
    openGraph: { description, locale, type: "website", url: `/${locale}${suffix}` },
  };
}

const SCHEMA_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

/** schema.org Dentist data built only from the clinic's real details. */
export function clinicJsonLd(clinic: Clinic, locale: Locale) {
  const address = {
    "@type": "PostalAddress",
    ...(clinic.address_line && { streetAddress: clinic.address_line }),
    ...(clinic.postal_code && { postalCode: clinic.postal_code }),
    ...(clinic.city && { addressLocality: clinic.city }),
    ...(clinic.country && { addressCountry: clinic.country }),
  };
  return {
    "@context": "https://schema.org",
    "@type": "Dentist",
    name: clinic.name,
    url: `${siteUrl()}/${locale}`,
    ...(clinic.phone && { telephone: clinic.phone }),
    ...(clinic.email && { email: clinic.email }),
    ...(Object.keys(address).length > 1 && { address }),
    openingHoursSpecification: clinic.opening_hours.map((h) => ({
      "@type": "OpeningHoursSpecification",
      dayOfWeek: `https://schema.org/${SCHEMA_DAYS[h.weekday]}`,
      opens: h.start,
      closes: h.end,
    })),
  };
}

/** Serialise JSON-LD safely for a <script> tag. */
export function jsonLdScript(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}

/** "Smile Studio – dental clinic in Prishtina. …" from the clinic's real name and city. */
export function siteDescription(t: Dictionary, clinic: Clinic | null): string {
  const inCity = clinic?.city ? interpolate(t.meta.inCity, { city: clinic.city }) : "";
  return interpolate(t.meta.description, { clinic: clinic?.name ?? t.meta.dentalClinic, inCity });
}
