// Server-side access to the Django public website API. Data is cached for
// five minutes; a failure returns null so pages can show a clear notice.

import type { Article, ArticleCategory, Clinic, Dentist, Service } from "./types";

const API_URL = (process.env.DJANGO_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const REVALIDATE_SECONDS = 300;

export function clinicSlug(): string | null {
  return process.env.CLINIC_SLUG || null;
}

async function get<T>(path: string): Promise<T | null> {
  const slug = clinicSlug();
  if (!slug) return null;
  try {
    const response = await fetch(`${API_URL}/api/public/clinics/${encodeURIComponent(slug)}/${path}`, {
      next: { revalidate: REVALIDATE_SECONDS },
    });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

export const getClinic = () => get<Clinic>("");

export async function getServices() {
  return get<{ currency: string; services: Service[] }>("services/");
}

export async function getDentists() {
  return (await get<{ dentists: Dentist[] }>("dentists/"))?.dentists ?? null;
}

/**
 * Published articles in `language`; if there are none in that language, all
 * languages (each article carries its language so the page can say so).
 */
export async function getArticles(language: string, category?: ArticleCategory) {
  const filter = category ? `&category=${category}` : "";
  const own = await get<{ articles: Article[] }>(`articles/?language=${language}${filter}`);
  if (own === null || own.articles.length) return own?.articles ?? null;
  const any = await get<{ articles: Article[] }>(`articles/${category ? `?category=${category}` : ""}`);
  return any?.articles ?? null;
}
