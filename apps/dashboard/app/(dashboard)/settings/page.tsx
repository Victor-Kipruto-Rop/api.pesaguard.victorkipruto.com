import { ContractError } from "@/components/domain/ContractError";
import { Card } from "@/components/ui/Card";
import { getSettings } from "@/lib/api/contracts";
import { SettingsForm } from "@/components/settings/SettingsForm";

export default async function SettingsPage() {
  try {
    const settings = await getSettings();
    const entries = Object.entries(settings).filter(([key]) => !key.toLowerCase().includes("secret") && !key.toLowerCase().includes("credential"));
    return <div className="page-shell"><header className="page-header"><div><p className="eyebrow">Workspace / Settings</p><h1>Organization settings</h1><p className="muted">Non-sensitive settings returned for the authenticated tenant.</p></div></header><div className="overview-grid"><Card eyebrow="Configuration" title="Current values"><dl className="settings-list">{entries.map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{typeof value === "object" ? "Configured" : String(value ?? "Not set")}</dd></div>)}</dl></Card><Card eyebrow="Locale" title="Update preferences"><SettingsForm preferredLocale={settings.preferred_locale} /></Card></div></div>;
  } catch (error) {
    return <div className="page-shell"><ContractError message={error instanceof Error ? error.message : "Settings data is unavailable."} /></div>;
  }
}
