import Link from "next/link";
import { navigation } from "@/config/navigation";
import { siteConfig } from "@/config/site";

/**
 * Site footer.
 *
 * Columns come from `config/navigation` so the footer cannot drift away from
 * the header. The status line stays deliberately vague about uptime: the
 * marketing site only knows about the backend when its health probe answers,
 * and a footer is the wrong place to claim availability we have not measured.
 */
export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-top">
        <div className="footer-brand">
          <Link aria-label="PesaGuard home" className="brand" href="/">
            <span aria-hidden="true" className="brand-mark">
              PG
            </span>
            <span>PesaGuard</span>
          </Link>
          <p className="footer-note">{siteConfig.tagline}</p>
          <p className="footer-note">
            {siteConfig.maturity} {siteConfig.scope}
          </p>
          <Link className="footer-status-line" href="/status">
            <span aria-hidden="true" className="status-dot status-dot-muted" />
            <span>System status</span>
            <span className="muted">Values appear when the health probe answers</span>
          </Link>
        </div>

        {navigation.footer.map((group) => (
          <div className="footer-column" key={group.title}>
            <h2>{group.title}</h2>
            {group.links.map((link) => (
              <Link href={link.href} key={link.href}>
                {link.label}
              </Link>
            ))}
          </div>
        ))}
      </div>

      <div className="container footer-bottom">
        <span>
          © {new Date().getFullYear()} PesaGuard · {siteConfig.region}
        </span>
        <span className="footer-legal">
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
          <Link href="/cookies">Cookies</Link>
          <a href={siteConfig.repository}>Source repository</a>
        </span>
      </div>
    </footer>
  );
}