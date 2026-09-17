import type { Availability } from "@/types/content";

/** A single destination inside the header navigation. */
export type NavLink = {
  label: string;
  href: string;
  description?: string;
  /** Set when the destination describes something we do not ship today. */
  availability?: Availability;
};

/** A titled column inside a mega-menu panel. */
export type NavGroup = {
  title: string;
  links: NavLink[];
};

/**
 * A top-level navigation entry.
 *
 * `href` always renders as a real link so keyboard users and crawlers can reach
 * the section index page. `groups` adds a disclosure button that opens the
 * mega-menu panel for that section.
 */
export type NavItem = {
  label: string;
  href: string;
  groups?: NavGroup[];
  foot?: NavLink;
};

/** A grouped column in the site footer. */
export type FooterGroup = {
  title: string;
  links: NavLink[];
};
