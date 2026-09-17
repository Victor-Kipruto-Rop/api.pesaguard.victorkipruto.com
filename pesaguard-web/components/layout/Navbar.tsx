"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ChevronDown, Menu, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { navigation } from "@/config/navigation";
import type { NavItem } from "@/types/navigation";

/** Stable id per menu so `aria-controls` can point at the mega-menu panel. */
function panelId(href: string): string {
  return `mega-${href.replace(/[^a-z0-9]+/gi, "-")}`;
}

/**
 * Site header.
 *
 * Every top-level entry is a real link to the section index page, so the menu
 * works with JavaScript disabled and with a keyboard alone. Entries that carry
 * `groups` also render a disclosure button whose panel toggles `data-open`; the
 * stylesheet additionally reveals the panel on hover and focus-within. No
 * destination appears here that is not an existing route.
 */
export function Navbar() {
  const pathname = usePathname();
  const [openPanel, setOpenPanel] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [elevated, setElevated] = useState(false);

  useEffect(() => {
    const onScroll = () => setElevated(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (openPanel === null) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpenPanel(null);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [openPanel]);

  const isCurrent = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <header className="site-header" data-elevated={elevated}>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <div className="container header-inner">
        <Link aria-label="PesaGuard home" className="brand" href="/">
          <span aria-hidden="true" className="brand-mark">
            PG
          </span>
          <span>PesaGuard</span>
          <span className="brand-sub">M-Pesa reconciliation</span>
        </Link>

        <nav aria-label="Main navigation" className="primary-nav hide-mobile">
          <ul className="nav-list">
            {navigation.primary.map((item: NavItem) => {
              const open = openPanel === item.label;
              return (
                <li className="nav-item" data-open={open ? "true" : "false"} key={item.href}>
                  <span className="nav-nested">
                    <Link
                      aria-current={isCurrent(item.href) ? "page" : undefined}
                      className="nav-link"
                      href={item.href}
                    >
                      {item.label}
                    </Link>
                    {item.groups?.length ? (
                      <button
                        aria-controls={panelId(item.href)}
                        aria-expanded={open}
                        aria-label={`${open ? "Close" : "Open"} ${item.label} menu`}
                        className="nav-trigger"
                        onClick={() => setOpenPanel(open ? null : item.label)}
                        type="button"
                      >
                        <ChevronDown aria-hidden="true" size={14} />
                      </button>
                    ) : null}
                  </span>

                  {item.groups?.length ? (
                    <div className="mega" id={panelId(item.href)}>
                      <div className={`mega-grid${item.groups.length > 2 ? " mega-wide" : ""}`}>
                        {item.groups.map((group) => (
                          <div className="mega-column" key={group.title}>
                            <p className="mega-title">{group.title}</p>
                            {group.links.map((link) => (
                              <Link className="mega-link" href={link.href} key={link.href}>
                                <strong>{link.label}</strong>
                                {link.description ? <span>{link.description}</span> : null}
                              </Link>
                            ))}
                          </div>
                        ))}
                      </div>
                      {item.foot ? (
                        <div className="mega-foot">
                          <Link className="text-link" href={item.foot.href}>
                            {item.foot.label}
                          </Link>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="header-actions">
          <Link className="header-status" href="/status">
            <span aria-hidden="true" className="status-dot status-dot-muted" />
            Status
          </Link>
          <span className="hide-mobile">
            <Button href="/contact/sales" size="sm">
              Talk to us
            </Button>
          </span>
          <button
            aria-controls="mobile-navigation"
            aria-expanded={drawerOpen}
            aria-label={drawerOpen ? "Close menu" : "Open menu"}
            className="nav-toggle show-mobile"
            onClick={() => setDrawerOpen(!drawerOpen)}
            type="button"
          >
            {drawerOpen ? <X aria-hidden="true" size={18} /> : <Menu aria-hidden="true" size={18} />}
          </button>
        </div>
      </div>

      {drawerOpen ? (
        <div className="mobile-nav show-mobile" id="mobile-navigation">
          <div className="container mobile-nav-inner">
            {navigation.primary.map((item) => (
              <div className="mobile-group" key={item.href}>
                <p className="mobile-group-title">{item.label}</p>
                <Link className="mobile-link" href={item.href} onClick={() => setDrawerOpen(false)}>
                  {item.label} overview
                </Link>
                {item.groups?.flatMap((group) =>
                  group.links.map((link) => (
                    <Link
                      className="mobile-link"
                      href={link.href}
                      key={`${item.href}-${link.href}`}
                      onClick={() => setDrawerOpen(false)}
                    >
                      {link.label}
                    </Link>
                  )),
                )}
              </div>
            ))}
            <div className="mobile-actions">
              <Button block href="/contact/sales">
                Talk to us
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </header>
  );
}