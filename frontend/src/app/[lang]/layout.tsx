import type { Metadata, Viewport } from "next";
import { Cormorant_Garamond, Instrument_Sans } from "next/font/google";
import { notFound } from "next/navigation";

import { ChatLauncher } from "@/components/chat/ChatLauncher";
import { ChatProvider } from "@/components/chat/ChatProvider";
import { Footer } from "@/components/layout/Footer";
import { Header } from "@/components/layout/Header";
import { getDictionary } from "@/dictionaries";
import { clinicSlug, getClinic } from "@/lib/api";
import { LOCALES, isLocale } from "@/lib/locale";
import { pageMetadata, siteDescription, siteUrl } from "@/lib/seo";

import "../globals.css";

const display = Cormorant_Garamond({
  subsets: ["latin", "latin-ext"],
  weight: ["500", "600"],
  variable: "--font-cormorant",
  display: "swap",
});

const sans = Instrument_Sans({
  subsets: ["latin", "latin-ext"],
  variable: "--font-instrument",
  display: "swap",
});

export function generateStaticParams() {
  return LOCALES.map((lang) => ({ lang }));
}

export const viewport: Viewport = { themeColor: "#f8f5ee" };

export async function generateMetadata({ params }: LayoutProps<"/[lang]">): Promise<Metadata> {
  const { lang } = await params;
  if (!isLocale(lang)) return {};
  const t = getDictionary(lang);
  const clinic = await getClinic();
  const name = clinic?.name ?? t.meta.dentalClinic;
  return {
    metadataBase: new URL(siteUrl()),
    title: { default: name, template: `%s · ${name}` },
    applicationName: name,
    icons: { icon: "/favicon.svg" },
    ...pageMetadata(lang, "", null, siteDescription(t, clinic)),
  };
}

export default async function LocaleLayout({ children, params }: LayoutProps<"/[lang]">) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const t = getDictionary(lang);
  const clinic = await getClinic();

  return (
    <html lang={lang} className={`${display.variable} ${sans.variable}`}>
      <body className="min-h-dvh">
        <ChatProvider
          locale={lang}
          t={t.chat}
          clinic={{
            slug: clinicSlug(),
            name: clinic?.name ?? t.meta.dentalClinic,
            phone: clinic?.phone ?? "",
            timezone: clinic?.timezone ?? "UTC",
          }}
        >
          <Header locale={lang} t={t} clinic={clinic} />
          <main id="main" tabIndex={-1} className="focus:outline-none">
            {children}
          </main>
          <Footer locale={lang} t={t} clinic={clinic} />
          <ChatLauncher />
        </ChatProvider>
      </body>
    </html>
  );
}
