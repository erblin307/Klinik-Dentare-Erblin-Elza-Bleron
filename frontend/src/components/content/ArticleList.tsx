import type { Article } from "@/lib/types";

/** Questions as native disclosure widgets: accessible and usable without JavaScript. */
export function ArticleAccordion({ articles }: { articles: Article[] }) {
  return (
    <div className="divide-y divide-line border-y border-line">
      {articles.map((article) => (
        <details key={article.id} className="group py-5" lang={article.language}>
          <summary className="flex cursor-pointer list-none items-start justify-between gap-6 text-xl leading-snug marker:hidden md:text-2xl [&::-webkit-details-marker]:hidden">
            <span className="font-display">{article.title}</span>
            <span
              aria-hidden="true"
              className="mt-1 text-2xl leading-none text-brass transition-transform duration-200 group-open:rotate-45"
            >
              +
            </span>
          </summary>
          <p className="prose-clinic mt-4 max-w-3xl text-muted">{article.content}</p>
        </details>
      ))}
    </div>
  );
}
