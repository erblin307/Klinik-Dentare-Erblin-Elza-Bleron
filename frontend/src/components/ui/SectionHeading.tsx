import type { ReactNode } from "react";

type Props = {
  index?: string;
  eyebrow: string;
  title: string;
  lead?: string;
  id?: string;
  action?: ReactNode;
};

/** Editorial section header: numbered label on the left, serif title on the right. */
export function SectionHeading({ index, eyebrow, title, lead, id, action }: Props) {
  return (
    <header className="mb-10 grid gap-4 border-t border-line pt-6 md:mb-14 md:grid-cols-12 md:gap-8">
      <p className="text-xs font-medium tracking-[0.18em] text-brass uppercase md:col-span-3">
        {index && <span className="mr-3 tabular-nums">{index}</span>}
        {eyebrow}
      </p>
      <div className="md:col-span-9">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <h2 id={id} className="max-w-3xl text-4xl leading-[1.05] text-ink md:text-5xl">
            {title}
          </h2>
          {action}
        </div>
        {lead && <p className="mt-4 max-w-2xl text-lg leading-relaxed text-muted">{lead}</p>}
      </div>
    </header>
  );
}
