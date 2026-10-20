import type { MetadataRoute } from "next";

import { LOCALES } from "@/lib/locale";
import { PAGES } from "@/lib/navigation";
import { siteUrl } from "@/lib/seo";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = siteUrl();
  return PAGES.flatMap((page) =>
    LOCALES.map((locale) => ({
      url: `${base}/${locale}${page ? `/${page}` : ""}`,
      changeFrequency: "weekly" as const,
      priority: page === "" ? 1 : 0.7,
      alternates: {
        languages: Object.fromEntries(LOCALES.map((code) => [code, `${base}/${code}${page ? `/${page}` : ""}`])),
      },
    })),
  );
}
