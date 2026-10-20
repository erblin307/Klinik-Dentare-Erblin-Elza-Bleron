import { NextResponse, type NextRequest } from "next/server";

import { isLocale, negotiateLocale } from "@/lib/locale";

/** Send visitors without a language in the URL to their preferred one. */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (isLocale(pathname.split("/")[1] ?? "")) return NextResponse.next();
  const url = request.nextUrl.clone();
  url.pathname = `/${negotiateLocale(request.headers.get("accept-language"))}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(url);
}

export const config = {
  // Not for the API rewrites, Next.js internals or files such as robots.txt.
  matcher: ["/((?!api/|_next/|.*\\..*).*)"],
};
