import type { Metadata } from "next";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { organizationJsonLd } from "@/lib/seo/structured-data";
import { siteConfig } from "@/config/site";
import "@/styles/globals.css";
import "@/styles/home.css";
import "@/styles/api.css";
import "@/styles/docs.css";
import "@/styles/sections.css";
import "@/styles/animations.css";
import "@/styles/typography.css";

export const metadata: Metadata = {
  title: { default: "PesaGuard | Trust infrastructure for African payments", template: "%s | PesaGuard" },
  description: siteConfig.description,
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationJsonLd()) }} />
        <Navbar />
        <main id="main-content">{children}</main>
        <Footer />
      </body>
    </html>
  );
}

