import Link from "next/link";
import type { ComponentProps } from "react";

const VARIANTS = {
  primary:
    "bg-forest text-ivory hover:bg-forest-deep shadow-[0_1px_0_rgba(0,0,0,0.04)]",
  secondary: "border border-forest/25 text-forest hover:border-forest hover:bg-forest/[0.04]",
  light: "bg-ivory text-forest hover:bg-paper",
} as const;

export const buttonClasses = (variant: keyof typeof VARIANTS = "primary") =>
  `inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-6 py-3 text-sm font-medium tracking-wide transition-colors ${VARIANTS[variant]}`;

type Props = ComponentProps<typeof Link> & { variant?: keyof typeof VARIANTS };

export function ButtonLink({ variant = "primary", className = "", ...props }: Props) {
  return <Link {...props} className={`${buttonClasses(variant)} ${className}`} />;
}

/** Understated text link with an arrow, used for "see all" links. */
export function ArrowLink({ className = "", children, ...props }: ComponentProps<typeof Link>) {
  return (
    <Link
      {...props}
      className={`group inline-flex items-center gap-2 text-sm font-medium text-forest underline decoration-forest/30 underline-offset-[6px] transition hover:decoration-forest ${className}`}
    >
      {children}
      <span aria-hidden="true" className="transition-transform group-hover:translate-x-0.5">
        →
      </span>
    </Link>
  );
}
