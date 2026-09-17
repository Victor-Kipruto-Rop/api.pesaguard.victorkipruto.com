import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  if (request.cookies.has("pesaguard_session")) return NextResponse.next();
  const login = new URL("/login", request.url);
  login.searchParams.set("next", `${request.nextUrl.pathname}${request.nextUrl.search}`);
  return NextResponse.redirect(login);
}

export const config = { matcher: ["/overview/:path*", "/transactions/:path*", "/reconciliation/:path*", "/anomalies/:path*", "/reports/:path*", "/alerts/:path*", "/integrations/:path*", "/customers/:path*", "/audit/:path*", "/developer/:path*", "/operations/:path*", "/settings/:path*"] };
