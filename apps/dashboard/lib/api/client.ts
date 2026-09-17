import { ApiError } from "@/lib/api/errors";

type ApiErrorBody = { code?: string; message?: string; error?: string; requestId?: string };

export type AuthResponse = { token: string; user_id: string; username: string; tenant_id: string; roles: string[]; expires_in: number };

const apiUrl = "";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, { ...init, credentials: "include", headers: { "Content-Type": "application/json", "X-Request-ID": crypto.randomUUID(), ...(init.headers ?? {}) } });
  const body = await response.json().catch(() => ({})) as ApiErrorBody;
  if (!response.ok) throw new ApiError(response.status, { code: body.code ?? body.error ?? "REQUEST_FAILED", message: body.message ?? `Request failed (${response.status})`, requestId: body.requestId });
  return body as T;
}

export const apiClient = {
  login(username: string, password: string) { return request<{ status: "authenticated" }>(`${apiUrl}/api/auth/login`, { method: "POST", body: JSON.stringify({ username, password }) }); },
  verify() { return request<{ user_id: string; username: string; tenant_id: string; roles: string[]; permissions: string[] }>(`${apiUrl}/api/auth/verify`); },
  logout() { return request<{ status: "signed_out" }>(`${apiUrl}/api/auth/logout`, { method: "POST" }); },
  backend<T>(path: string, init: RequestInit = {}) { return request<T>(`${apiUrl}/api/backend${path}`, init); },
};
