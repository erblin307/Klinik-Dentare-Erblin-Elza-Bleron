"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { href, type PagePath } from "@/lib/navigation";

type Props = {
  locale: string;
  items: { path: PagePath; label: string }[];
  orientation: "horizontal" | "vertical";
  onNavigate?: () => void;
};

export function NavLinks({ locale, items, orientation, onNavigate }: Props) {
  const pathname = usePathname();
  return (
    <ul className={orientation === "horizontal" ? "flex items-center gap-7" : "flex flex-col"}>
      {items.map((item) => {
        const target = href(locale, item.path);
        const current = item.path ? pathname === target || pathname.startsWith(`${target}/`) : pathname === target;
        return (
          <li key={item.path}>
            <Link
              href={target}
              onClick={onNavigate}
              aria-current={current ? "page" : undefined}
              className={
                orientation === "horizontal"
                  ? `text-sm transition-colors hover:text-forest ${current ? "text-forest underline decoration-brass decoration-1 underline-offset-[10px]" : "text-ink/80"}`
                  : `block border-b border-line py-4 font-display text-3xl ${current ? "text-forest" : "text-ink"}`
              }
            >
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
