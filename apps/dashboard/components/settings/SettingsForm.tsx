"use client";

import { FormEvent, useState } from "react";
import { updateSettings } from "@/lib/api/mutations";

export function SettingsForm({ preferredLocale = "" }: { preferredLocale?: string }) {
  const [locale, setLocale] = useState(preferredLocale);
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setMessage(null);
    try { await updateSettings({ preferred_locale: locale }); setMessage("Settings updated"); } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to update settings"); } finally { setPending(false); }
  }
  return <form className="settings-form" onSubmit={submit}><label className="field">Preferred locale<input value={locale} onChange={(event) => setLocale(event.target.value)} placeholder="en" /></label><button className="button primary" disabled={pending} type="submit">{pending ? "Updating..." : "Update settings"}</button>{message && <p className="form-message" role="status">{message}</p>}</form>;
}
