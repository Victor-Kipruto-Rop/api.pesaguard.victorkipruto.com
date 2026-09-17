"use client";

import { useState } from "react";
import { addDiscrepancyNote, assignDiscrepancy, resolveDiscrepancy } from "@/lib/api/mutations";

export function AnomalyActions({ id }: { id: string }) {
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  async function resolve() {
    if (!window.confirm("Resolve this anomaly? This creates an audit event.")) return;
    setPending(true); setMessage(null);
    try { await resolveDiscrepancy(id); setMessage("Resolved"); } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to resolve"); } finally { setPending(false); }
  }
  async function addNote() {
    const note = window.prompt("Audit note");
    if (!note?.trim()) return;
    setPending(true); setMessage(null);
    try { await addDiscrepancyNote(id, note.trim()); setMessage("Note saved"); } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to save note"); } finally { setPending(false); }
  }
  async function assign() {
    const assignee = window.prompt("Assignee identifier");
    if (!assignee?.trim()) return;
    setPending(true); setMessage(null);
    try { await assignDiscrepancy(id, assignee.trim()); setMessage("Assigned"); } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to assign"); } finally { setPending(false); }
  }
  return <div className="row-actions"><button className="table-action" disabled={pending} onClick={resolve}>Resolve</button><button className="table-action" disabled={pending} onClick={addNote}>Note</button><button className="table-action" disabled={pending} onClick={assign}>Assign</button>{message && <span className="action-message" role="status">{message}</span>}</div>;
}
