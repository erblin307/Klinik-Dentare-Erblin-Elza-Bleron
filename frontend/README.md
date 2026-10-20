# Website (Next.js)

Public website and chat widget of the clinic. See `../ARCHITECTURE.md`
("Website") for the design and `../PROJECT_RULES.md` for the rules.

## Requirements

- Node.js 22.6+ (tested with 22.22)
- The Django backend running with a clinic (`CLINIC_SLUG`) that has services,
  dentists, working hours and published knowledge articles

## Setup

```bash
cd frontend
npm ci
cp .env.example .env.local     # set CLINIC_SLUG and DJANGO_API_URL
npm run dev                    # http://localhost:3000 → redirects to /sq, /en or /de
```

| Variable | Purpose |
| -------- | ------- |
| `DJANGO_API_URL` | Backend address, used only by the Next.js server (pages and API forwarding) |
| `CLINIC_SLUG` | Which clinic the site shows (`Clinic.slug`) |
| `NEXT_PUBLIC_SITE_URL` | Public URL for canonical links and the sitemap |

No API keys are needed: the site only reads public clinic data, and the
browser reaches Django's chat and availability endpoints through this site's
own origin (`/api/chat/*`, `/api/public/*`, forwarded in `next.config.ts`).

## Checks

```bash
npm test           # unit tests (Node's built-in test runner, no extra packages)
npm run lint       # ESLint with Next.js, React Hooks and accessibility rules
npm run typecheck
npm run build      # works without a running backend; pages refresh every 5 minutes
```

## Structure

```
src/
  app/[lang]/          pages: home, services, dentists, about, faq, contact, book
  components/          layout (header, footer, navigation), ui, content, booking, chat
  dictionaries/        interface texts in sq, en, de (clinic facts come from the API)
  lib/                 API client, formatting, locale, SEO, chat client and state
  proxy.ts             redirects "/" to the visitor's language
public/photos/         the clinic's own photos (see README there)
```

## Photos

See `public/photos/README.md` for the photo slots and recommended sizes.
Page photos are set in `src/lib/photos.ts`; a dentist's portrait is set in
the Django admin (Dentist → Photo, a path such as `/photos/dentists/arta.jpg`).
Everything in `public/photos/demo/` is a **demo image** and is always shown
with a "Demo photo" label; put the clinic's own photos outside `demo/`.
Dentists without a photo are shown with a monogram.
