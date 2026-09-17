import { NextRequest, NextResponse } from "next/server";

const apiUrl = (process.env.PESAGUARD_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "https://api.pesaguard.victorkipruto.com").replace(/\/$/, "");
type RouteProps = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, { params }: RouteProps) {
  const token = request.cookies.get("pesaguard_session")?.value;
  if (!token) return NextResponse.json({ code: "NOT_AUTHENTICATED", message: "Authentication required." }, { status: 401 });
  const { path } = await params;
  const upstream = await fetch(`${apiUrl}/${path.join("/")}${request.nextUrl.search}`, {
    method: request.method,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": request.headers.get("content-type") ?? "application/json", "X-Request-ID": crypto.randomUUID() },
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
    cache: "no-store",
  }).catch(() => null);
  if (!upstream) return NextResponse.json({ code: "UPSTREAM_UNAVAILABLE", message: "Backend service is unavailable." }, { status: 503 });
  const contentType = upstream.headers.get("content-type") ?? "application/json";
  const body = await upstream.arrayBuffer();
  return new NextResponse(body, { status: upstream.status, headers: { "Content-Type": contentType } });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
