"use client";

import { useState } from "react";
import { replayDeadLetter } from "@/lib/api/mutations";

export function DlqActions({ id }: { id: string }) {
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  async function replay() {
    if (!window.confirm("Queue this dead-letter event for replay? The operation is audited and retry-limited.")) return;
    setPending(true); setMessage(null);
    try { await replayDeadLetter(id, "operator replay from dashboard"); setMessage("Queued"); } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to replay"); } finally { setPending(false); }
  }
  return <div className="row-actions"><button className="table-action" disabled={pending} onClick={replay}>Replay</button>{message && <span className="action-message" role="status">{message}</span>}</div>;
}
