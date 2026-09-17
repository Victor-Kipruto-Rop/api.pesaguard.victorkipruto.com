"use client";

import { useEffect, useState } from "react";

type HealthState = "checking" | "operational" | "degraded" | "disconnected";

export function SystemHeartbeat() {
  const [state, setState] = useState<HealthState>("checking");

  useEffect(() => {
    let active = true;
    fetch("/api/health", { cache: "no-store" }).then((response) => { if (!active) return; setState(response.ok ? "operational" : "degraded"); }).catch(() => { if (active) setState("disconnected"); });
    return () => { active = false; };
  }, []);

  const label = state === "checking" ? "Checking" : state[0].toUpperCase() + state.slice(1);
  return <span className={`live live-${state}`}><span className="live-dot" />{label}</span>;
}
