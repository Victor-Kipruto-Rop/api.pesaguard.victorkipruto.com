import type { Metadata } from "next";
import { seoConfig } from "@/config/seo";
import { siteConfig } from "@/config/site";

function absoluteUrl(path: string): string {
  const normalised = path.startsWith("/") ? path : `/${path}`;
  return new URL(normalised, siteConfig.url).toString();
}

/**
 * Builds page metadata with a canonical URL for the page it belongs to.
 *
 * Pass the route `path` so each page canonicalises to itself instead of the
 * site root, which would otherwise tell crawlers that every page is a duplicate.
 */
export function pageMetadata(
  title: string,
  description: string = siteConfig.description,
  path: string = "/",
): Metadata {
  const canonical = absoluteUrl(path);

  return {
    title,
    description,
    alternates: { canonical },
    openGraph: {
      title,
      description,
      url: canonical,
      siteName: siteConfig.name,
      type: seoConfig.type,
      locale: seoConfig.locale,
    },
    twitter: {
      card: seoConfig.twitterCard,
      title,
      description,
    },
  };
}
