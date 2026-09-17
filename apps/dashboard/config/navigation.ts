import type { Permission } from "@/config/permissions";

export type NavigationItem = { label: string; href: string; permission?: Permission; children?: NavigationItem[] };

export const navigation: NavigationItem[] = [
  { label: "Overview", href: "/overview" },
  { label: "Transactions", href: "/transactions", permission: "transactions.read", children: [{ label: "Pending", href: "/transactions/pending" }, { label: "Failed", href: "/transactions/failed" }, { label: "Flagged", href: "/transactions/flagged" }, { label: "Search", href: "/transactions/search" }] },
  { label: "Reconciliation", href: "/reconciliation", permission: "reconciliation.read" },
  { label: "Anomalies", href: "/anomalies", permission: "anomalies.read" },
  { label: "Reports", href: "/reports", permission: "reports.read" },
  { label: "Alerts", href: "/alerts" },
  { label: "Integrations", href: "/integrations", permission: "integrations.read" },
  { label: "Customers", href: "/customers" },
  { label: "Audit", href: "/audit", permission: "audit.read" },
  { label: "Developer", href: "/developer", permission: "developer.api_keys.manage" },
  { label: "Operations", href: "/operations", permission: "operations.read" },
  { label: "Settings", href: "/settings", permission: "settings.manage" },
];
