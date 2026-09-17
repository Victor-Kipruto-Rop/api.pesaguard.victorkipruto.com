import { NextResponse } from "next/server";

const apiUrl = (process.env.PESAGUARD_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "https://api.pesaguard.victorkipruto.com").replace(/\/$/, "");
const cookieName = "pesaguard_session";

type LoginBody = { username?: unknown; password?: unknown };
type BackendLogin = { token?: string; expires_in?: number };

export async function POST(request: Request) {
  const payload = await request.json().catch(() => null) as LoginBody | null;
  if (typeof payload?.username !== "string" || typeof payload.password !== "string" || !payload.username || !payload.password) {
    return NextResponse.json({ code: "INVALID_REQUEST", message: "Username and password are required." }, { status: 400 });
  }

  const upstream = await fetch(`${apiUrl}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Request-ID": crypto.randomUUID() },
    body: JSON.stringify({ username: payload.username, password: payload.password }),
    cache: "no-store",
  }).catch(() => null);

  if (!upstream) return NextResponse.json({ code: "AUTH_UNAVAILABLE", message: "Authentication service is unavailable." }, { status: 503 });
  const body = await upstream.json().catch(() => ({})) as BackendLogin & { message?: string; error?: string };
  if (!upstream.ok || typeof body.token !== "string") {
    return NextResponse.json({ code: body.error ?? "AUTH_FAILED", message: body.message ?? "Unable to sign in." }, { status: upstream.status || 502 });
  }

  const response = NextResponse.json({ status: "authenticated" });
  response.cookies.set(cookieName, body.token, { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: Math.min(body.expires_in ?? 86400, 86400) });
  return response;
}
