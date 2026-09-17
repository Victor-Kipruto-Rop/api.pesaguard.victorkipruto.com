import { NextResponse } from "next/server";

const apiUrl = (process.env.PESAGUARD_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "https://api.pesaguard.victorkipruto.com").replace(/\/$/, "");

export async function GET() {
  const upstream = await fetch(`${apiUrl}/health`, { headers: { "X-Request-ID": crypto.randomUUID() }, cache: "no-store" }).catch(() => null);
  if (!upstream) return NextResponse.json({ status: "unavailable" }, { status: 503 });
  const body = await upstream.json().catch(() => ({ status: "unknown" }));
  return NextResponse.json(body, { status: upstream.status });
}
