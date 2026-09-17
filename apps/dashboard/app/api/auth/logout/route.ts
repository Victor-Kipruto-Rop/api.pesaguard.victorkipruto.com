import { NextRequest, NextResponse } from "next/server";

const apiUrl = (process.env.PESAGUARD_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "https://api.pesaguard.victorkipruto.com").replace(/\/$/, "");

export async function POST(request: NextRequest) {
  const token = request.cookies.get("pesaguard_session")?.value;
  if (token) {
    await fetch(`${apiUrl}/auth/revoke`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, "X-Request-ID": crypto.randomUUID() }, body: JSON.stringify({ token }), cache: "no-store" }).catch(() => undefined);
  }
  const response = NextResponse.json({ status: "signed_out" });
  response.cookies.set("pesaguard_session", "", { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 0 });
  return response;
}
