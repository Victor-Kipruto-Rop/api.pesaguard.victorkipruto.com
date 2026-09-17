import { AppShell } from "@/components/shell/AppShell";
import { requireSession } from "@/lib/auth/server-session";

export default async function DashboardLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  await requireSession();
  return <AppShell>{children}</AppShell>;
}
