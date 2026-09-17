import { siteConfig } from "@/config/site";
import type { FaqItem } from "@/types/content";

type JsonLd = Record<string, unknown>;

/** Organisation identity used in the root layout. */
export function organizationJsonLd(): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: siteConfig.name,
    url: siteConfig.url,
    description: siteConfig.description,
    email: siteConfig.email,
    areaServed: "Kenya",
    sameAs: [siteConfig.repository],
  };
}

/**
 * Product description for the homepage.
 *
 * Deliberately minimal: no aggregate ratings, no prices, and no claims that the
 * repository cannot evidence.
 */
export function softwareApplicationJsonLd(): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: siteConfig.name,
    applicationCategory: "FinanceApplication",
    operatingSystem: "Web",
    description: siteConfig.description,
    url: siteConfig.url,
  };
}

/** FAQ markup for pages that render a question list. */
export function faqJsonLd(items: FaqItem[]): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  };
}

/** Breadcrumb trail markup; each entry needs a label and a site-relative href. */
export function breadcrumbJsonLd(trail: Array<{ label: string; href: string }>): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: trail.map((entry, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: entry.label,
      item: new URL(entry.href.startsWith("/") ? entry.href : `/${entry.href}`, siteConfig.url).toString(),
    })),
  };
}
