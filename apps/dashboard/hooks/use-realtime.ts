"use client";

import { useEffect, useState } from "react";
import type { RealtimeEvent, RealtimeEventType } from "@/lib/realtime/events";
import { RealtimeConnection, type ConnectionState } from "@/lib/realtime/websocket";

export function useRealtime(type?: RealtimeEventType, onEvent?: (event: RealtimeEvent) => void) {
  const [state, setState] = useState<ConnectionState>("disconnected");
  useEffect(() => {
    const connection = new RealtimeConnection(process.env.NEXT_PUBLIC_WS_URL, setState);
    const unsubscribe = type && onEvent ? connection.subscribe(type, onEvent) : undefined;
    connection.connect();
    return () => { unsubscribe?.(); connection.disconnect(); };
  }, [type, onEvent]);
  return { state, connected: state === "connected" };
}
