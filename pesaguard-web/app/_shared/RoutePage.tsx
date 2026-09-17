import { PageTemplate } from "@/components/PageTemplate";
import { pages } from "@/content/pages";
export function RoutePage({ slug, title, description }: { slug: string; title?: string; description?: string }) { const base = pages[slug] ?? pages.product; return <PageTemplate slug={slug} data={{ ...base, title: title ?? base.title, description: description ?? base.description }} />; }
