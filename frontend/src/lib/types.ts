// Shapes of the Django public website API (backend/apps/website/views.py).

export type Hours = { weekday: number; start: string; end: string };

export type Clinic = {
  name: string;
  slug: string;
  email: string;
  phone: string;
  address_line: string;
  postal_code: string;
  city: string;
  country: string;
  timezone: string;
  currency: string;
  opening_hours: Hours[];
  closures: { start: string; end: string }[];
};

export type Service = {
  id: number;
  name: string;
  description: string;
  duration_minutes: number;
  price: string | null;
  dentist_ids: number[];
};

export type Dentist = {
  id: number;
  name: string;
  specialty: string;
  bio: string;
  service_ids: number[];
  working_hours: Hours[];
};

export type ArticleCategory = "general" | "services" | "pricing" | "policies" | "faq";

export type Article = {
  id: number;
  title: string;
  content: string;
  category: ArticleCategory;
  language: string;
};

export type Slot = { start: string; end: string; dentist_id: number; dentist: string };
