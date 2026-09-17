import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { toSessionUser } from "@/lib/auth/session";
import type { SessionUser } from "@/types/user";

const apiUrl = (process.env.PESAGUARD_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "https://api.pesaguard.victorkipruto.com").replace(/\/$/, "");

export async function requireSession(): Promise<SessionUser> {
  const token = (await cookies()).get("pesaguard_session")?.value;
  if (!token) redirect("/login");
  const response = await fetch(`${apiUrl}/auth/verify`, { headers: { Authorization: `Bearer ${token}`, "X-Request-ID": crypto.randomUUID() }, cache: "no-store" }).catch(() => null);
  if (!response?.ok) redirect("/login?reason=session_expired");
  const body = await response.json().catch(() => null);
  if (!body?.user_id || !body?.tenant_id) redirect("/login?reason=invalid_session");
  return toSessionUser(body);
}
