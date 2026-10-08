"use client";

import { useCallback, useEffect, useRef } from "react";

import { sendRealtime } from "@/lib/ws";

const REPEAT_MS = 3_000; // re-announce at most this often while typing continues
const IDLE_MS = 3_000; // stop after this long without a keystroke

/** typing.start on the first keystroke (repeated every 3 s while typing), typing.stop after
 *  3 s idle, on send, on blur, and when leaving the chat. */
export function useTypingSender(conversationId: number): { typed: () => void; stopped: () => void } {
  const lastStart = useRef(0);
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopped = useCallback(() => {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = null;
    if (lastStart.current !== 0) {
      lastStart.current = 0;
      sendRealtime({ type: "typing.stop", payload: { conversation_id: conversationId } });
    }
  }, [conversationId]);

  const typed = useCallback(() => {
    const now = Date.now();
    if (now - lastStart.current > REPEAT_MS) {
      lastStart.current = now;
      sendRealtime({ type: "typing.start", payload: { conversation_id: conversationId } });
    }
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(stopped, IDLE_MS);
  }, [conversationId, stopped]);

  useEffect(() => stopped, [stopped]); // leaving the chat
  return { typed, stopped };
}
