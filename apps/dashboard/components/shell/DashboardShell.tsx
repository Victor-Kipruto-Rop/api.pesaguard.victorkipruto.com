"use client";

import { Activity, Bell, CircleGauge, Command, FileSearch, FileText, LayoutDashboard, LogOut, Menu, Network, Search, Settings, ShieldAlert, Users, WalletCards, Webhook, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { navigation } from "@/config/navigation";
import { apiClient } from "@/lib/api/client";
import { SystemHeartbeat } from "@/components/shell/SystemHeartbeat";

const icons = { Overview: LayoutDashboard, Transactions: WalletCards, Reconciliation: CircleGauge, Anomalies: ShieldAlert, Reports: FileText, Alerts: Webhook, Integrations: Network, Customers: Users, Audit: FileSearch, Developer: FileText, Operations: Activity, Settings };

export function DashboardShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => { setCollapsed(window.localStorage.getItem("pesaguard.sidebar.collapsed") === "true"); }, []);
  useEffect(() => { window.localStorage.setItem("pesaguard.sidebar.collapsed", String(collapsed)); }, [collapsed]);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setCommandOpen(true); } if (event.key === "Escape") { setCommandOpen(false); setNotificationsOpen(false); setWorkspaceOpen(false); } };
    window.addEventListener("keydown", onKeyDown); return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const filteredNavigation = navigation.filter((item) => item.label.toLowerCase().includes(query.toLowerCase()));
  async function signOut() { await apiClient.logout().catch(() => undefined); router.replace("/login"); }

  return <div className={`shell${collapsed ? " shell-collapsed" : ""}`}><aside className={`sidebar${mobileOpen ? " sidebar-open" : ""}`}><div className="sidebar-brand"><span className="brand-mark">P</span><span className="sidebar-wordmark">PesaGuard</span><button className="icon-button sidebar-close" type="button" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={18} /></button></div><nav aria-label="Primary navigation"><p className="nav-label">Control center</p><div className="nav-group">{navigation.map(({ label, href }) => { const Icon = icons[label as keyof typeof icons]; const active = pathname === href || pathname.startsWith(`${href}/`); return <Link className={`nav-item${active ? " active" : ""}`} href={href} key={href} onClick={() => setMobileOpen(false)}><Icon size={16} aria-hidden="true" /><span className="sidebar-wordmark">{label}</span></Link>; })}</div></nav><button className="collapse-button" type="button" onClick={() => setCollapsed((value) => !value)} aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}>{collapsed ? ">" : "<"}</button></aside>{mobileOpen && <button className="drawer-scrim" type="button" aria-label="Close navigation" onClick={() => setMobileOpen(false)} /> }<div className="shell-main"><header className="topbar"><button className="icon-button mobile-menu" type="button" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={18} /></button><button className="workspace-switcher" type="button" onClick={() => setWorkspaceOpen((value) => !value)} aria-expanded={workspaceOpen}><span><small>Workspace</small><strong>Organization context pending</strong></span><span aria-hidden="true">⌄</span></button><div className="top-actions"><button className="global-search" type="button" onClick={() => setCommandOpen(true)}><Search size={15} />Search <kbd>Ctrl K</kbd></button><SystemHeartbeat /><button className="icon-button" type="button" aria-label="Notifications" aria-expanded={notificationsOpen} onClick={() => setNotificationsOpen((value) => !value)}><Bell size={18} /></button><button className="avatar" type="button" aria-label="Open account menu" onClick={signOut}>?</button></div>{workspaceOpen && <div className="popover workspace-popover"><p className="eyebrow">Current organization</p><p className="muted">Organization context is provided by the authenticated session.</p></div>}{notificationsOpen && <div className="popover notifications-popover"><p className="eyebrow">Notifications</p><p className="muted">No notification feed contract is available yet.</p></div>}</header><main>{children}</main></div>{commandOpen && <div className="command-overlay" role="dialog" aria-modal="true" aria-labelledby="command-title" onClick={() => setCommandOpen(false)}><div className="command-dialog" onClick={(event) => event.stopPropagation()}><div className="command-heading"><Command size={16} /><h2 id="command-title">Command palette</h2><button className="icon-button" type="button" aria-label="Close command palette" onClick={() => setCommandOpen(false)}><X size={16} /></button></div><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search workspace views..." aria-label="Search commands" />{filteredNavigation.map(({ label, href }) => <Link className="command-item" href={href} key={href} onClick={() => setCommandOpen(false)}>{label}<span>Open</span></Link>)}<button className="command-item" type="button" onClick={signOut}><span><LogOut size={14} />Sign out</span><span>Action</span></button></div></div>}</div>;
}
