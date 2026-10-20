import type { ReactNode } from "react";

export function Notice({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "demo" }) {
  return (
    <div
      className={`rounded-sm border px-5 py-4 text-sm leading-relaxed ${
        tone === "demo" ? "border-brass/40 bg-paper text-ink" : "border-line bg-paper text-muted"
      }`}
    >
      {tone === "demo" && (
        <span className="mr-2 rounded-full bg-sand px-2 py-0.5 text-[11px] font-medium tracking-wider text-brass uppercase">
          Demo
        </span>
      )}
      {children}
    </div>
  );
}
