"use client";

import { FormEvent, useState } from "react";
import { apiClient } from "@/lib/api/client";
import { safePostLoginDestination } from "@/lib/auth/redirect";

export function LoginForm() {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(null); setPending(true);
    const form = new FormData(event.currentTarget);
    try {
      await apiClient.login(String(form.get("username") ?? ""), String(form.get("password") ?? ""));
      const requested = new URLSearchParams(window.location.search).get("next");
      window.location.assign(safePostLoginDestination(requested));
    }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to sign in."); setPending(false); }
  }

  return <form className="auth-form" onSubmit={submit}><label className="field">Username<input name="username" autoComplete="username" required /></label><label className="field">Password<input name="password" type="password" autoComplete="current-password" required /></label>{error && <p className="form-error" role="alert">{error}</p>}<button className="button primary" type="submit" disabled={pending}>{pending ? "Signing in..." : "Sign in"}</button></form>;
}
