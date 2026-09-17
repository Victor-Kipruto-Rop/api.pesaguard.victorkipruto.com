import { getBackendHealth } from "@/lib/api/client";
import { StatusBoard } from "@/components/sections/StatusBoard";
import { PageHero } from "@/components/sections/PageHero";
import { SectionShell } from "@/components/sections/SectionShell";
import { buildStatusSnapshot } from "@/lib/content/status";

export default async function Status() {
  const probe = await getBackendHealth();
  const snapshot = buildStatusSnapshot(probe);
  return (
    <>
      <PageHero
        title="Know what is running."
        lede="A transparent view of the services behind your payment operations."
        label="PesaGuard status"
      />
      <SectionShell>
        <StatusBoard snapshot={snapshot} />
        <p className="eyebrow" style={{ marginTop: 40 }}>
          {probe.status}
        </p>
      </SectionShell>
    </>
  );
}

