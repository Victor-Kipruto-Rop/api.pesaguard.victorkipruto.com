import { DashboardShell } from "@/components/shell/DashboardShell";

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  return <DashboardShell>{children}</DashboardShell>;
}
