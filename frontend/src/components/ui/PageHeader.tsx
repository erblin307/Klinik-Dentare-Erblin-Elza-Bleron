import { Container } from "./Container";

export function PageHeader({ eyebrow, title, lead }: { eyebrow: string; title: string; lead?: string }) {
  return (
    <section className="pt-14 pb-12 md:pt-24 md:pb-16">
      <Container>
        <p className="text-xs font-medium tracking-[0.18em] text-brass uppercase">{eyebrow}</p>
        <h1 className="mt-5 max-w-4xl text-5xl leading-[1.02] md:text-7xl">{title}</h1>
        {lead && <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted md:text-xl">{lead}</p>}
      </Container>
    </section>
  );
}
