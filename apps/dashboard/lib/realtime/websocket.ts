import type { RealtimeEvent, RealtimeEventType } from "@/lib/realtime/events";

export type ConnectionState = "unconfigured" | "connecting" | "connected" | "reconnecting" | "disconnected";
export type RealtimeListener = (event: RealtimeEvent) => void;

export class RealtimeConnection {
  private socket: WebSocket | null = null;
  private retryTimer: number | undefined;
  private heartbeatTimer: number | undefined;
  private retryCount = 0;
  private readonly seen = new Set<string>();
  private readonly listeners = new Map<RealtimeEventType, Set<RealtimeListener>>();
  private state: ConnectionState = "disconnected";
  private stateListener: (state: ConnectionState) => void;

  constructor(private readonly url: string | undefined, onState: (state: ConnectionState) => void) { this.stateListener = onState; }
  get connectionState() { return this.state; }
  connect() { if (!this.url) return this.setState("unconfigured"); this.setState(this.retryCount ? "reconnecting" : "connecting"); this.socket = new WebSocket(this.url); this.socket.onopen = () => { this.retryCount = 0; this.setState("connected"); this.startHeartbeat(); }; this.socket.onmessage = (message) => this.receive(message.data); this.socket.onerror = () => this.socket?.close(); this.socket.onclose = () => { this.stopHeartbeat(); if (this.state !== "disconnected") this.scheduleRetry(); }; }
  disconnect() { this.stopHeartbeat(); if (this.retryTimer) window.clearTimeout(this.retryTimer); this.retryTimer = undefined; this.socket?.close(); this.socket = null; this.setState("disconnected"); }
  subscribe(type: RealtimeEventType, listener: RealtimeListener) { const listeners = this.listeners.get(type) ?? new Set<RealtimeListener>(); listeners.add(listener); this.listeners.set(type, listeners); return () => listeners.delete(listener); }
  private receive(raw: string) { try { const event = JSON.parse(raw) as RealtimeEvent; if (!event.id || !event.type || this.seen.has(event.id)) return; this.seen.add(event.id); if (this.seen.size > 1000) this.seen.delete(this.seen.values().next().value as string); this.listeners.get(event.type)?.forEach((listener) => listener(event)); } catch { /* Ignore malformed events; transport remains alive. */ } }
  private scheduleRetry() { this.retryCount += 1; const delay = Math.min(30000, 500 * (2 ** Math.min(this.retryCount, 6))); this.setState("reconnecting"); this.retryTimer = window.setTimeout(() => this.connect(), delay); }
  private startHeartbeat() { this.heartbeatTimer = window.setInterval(() => { if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify({ type: "heartbeat" })); }, 30000); }
  private stopHeartbeat() { if (this.heartbeatTimer) window.clearInterval(this.heartbeatTimer); this.heartbeatTimer = undefined; }
  private setState(state: ConnectionState) { this.state = state; this.stateListener(state); }
}
