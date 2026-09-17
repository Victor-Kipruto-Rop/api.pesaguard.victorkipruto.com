import { NextRequest, NextResponse } from "next/server";

const apiUrl = (process.env.PESAGUARD_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "https://api.pesaguard.victorkipruto.com").replace(/\/$/, "");

export async function GET(request: NextRequest) {
  const token = request.cookies.get("pesaguard_session")?.value;
  if (!token) return NextResponse.json({ code: "NOT_AUTHENTICATED", message: "Authentication required." }, { status: 401 });
  const upstream = await fetch(`${apiUrl}/auth/verify`, { headers: { Authorization: `Bearer ${token}`, "X-Request-ID": crypto.randomUUID() }, cache: "no-store" }).catch(() => null);
  if (!upstream) return NextResponse.json({ code: "AUTH_UNAVAILABLE", message: "Authentication service is unavailable." }, { status: 503 });
  const body = await upstream.json().catch(() => ({}));
  return NextResponse.json(body, { status: upstream.status });
}
