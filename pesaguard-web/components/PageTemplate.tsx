import type { PageData } from "@/types/content";
import { PageHero } from "@/components/sections/PageHero";
import { AvailabilityBadge } from "@/components/ui/Badge";
import { SectionShell } from "@/components/sections/SectionShell";
import { Button } from "@/components/ui/Button";
import { SectionHeading } from "@/components/sections/SectionHeading";
import { FeatureGrid } from "@/components/sections/FeatureGrid";
import { StepFlow } from "@/components/sections/StepFlow";
import { ComparisonTable } from "@/components/sections/ComparisonTable";
export function PageTemplate({ data, slug }: { data: PageData; slug: string }) { return <><section className="page-hero"><div className="container"><Breadcrumbs trail={[{ label: "Home", href: "/" }, { label: data.label ?? data.title, href: `/${slug}` }]} /><p className="eyebrow">{data.label ?? "PesaGuard platform"}</p><h1>{data.title}</h1><p className="lede">{data.description}</p><Link className="button button-primary" href="/contact/sales">Talk to our team <ArrowUpRight size={17} /></Link></div></section><section className="section"><div className="container content-layout"><div className="content-main">{data.sections.map((section) => <article className="content-section" key={section.title}><p className="eyebrow">{slug.replaceAll("-", " ")}</p><h2>{section.title}</h2><p>{section.body}</p>{section.items && <ul className="check-list">{section.items.map((item) => <li key={item}><Check size={16} />{item}</li>)}</ul>}</article>)}</div><aside className="side-note"><span className="status-dot" /><strong>Designed for accountable operations</strong><p>Clear controls, useful evidence, and practical workflows for teams that move money.</p></aside></div></section></>; }
