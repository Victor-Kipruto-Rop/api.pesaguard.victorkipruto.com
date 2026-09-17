import { cookies } from "next/headers";
import { ApiError } from "@/lib/api/errors";

const apiUrl = (process.env.PESAGUARD_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "https://api.pesaguard.victorkipruto.com").replace(/\/$/, "");

export async function serverRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = (await cookies()).get("pesaguard_session")?.value;
  if (!token) throw new ApiError(401, { code: "NOT_AUTHENTICATED", message: "Authentication required." });
  const response = await fetch(`${apiUrl}${path}`, { ...init, cache: "no-store", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", "X-Request-ID": crypto.randomUUID(), ...(init.headers ?? {}) } }).catch(() => null);
  if (!response) throw new ApiError(503, { code: "UPSTREAM_UNAVAILABLE", message: "Backend service is unavailable." });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, { code: body.code ?? body.error ?? "REQUEST_FAILED", message: body.message ?? "Backend request failed.", requestId: body.requestId });
  return body as T;
}
