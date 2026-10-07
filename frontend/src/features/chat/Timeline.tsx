"use client";

import { ArrowDown } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { useMessages } from "@/store/messages";
import type { ConversationDetail } from "@/types/conversation";

import { buildRows } from "./build-rows";
import { ConversationHero } from "./ConversationHero";
import { MessageBubble } from "./MessageBubble";
import { DateSeparator, SystemMessage, UnreadDivider } from "./TimelineMarkers";

type TimelineProps = {
  conversation: ConversationDetail;
  myId: number;
  lastReadAtOpen: number; // frozen when the chat opened, so the divider doesn't jump while reading
};

const LOAD_OLDER_THRESHOLD_PX = 200;
const JUMP_BUTTON_THRESHOLD_PX = 300;
const READ_DEBOUNCE_MS = 300;

export function Timeline({ conversation, myId, lastReadAtOpen }: TimelineProps) {
  const conversationId = conversation.id;
  const thread = useMessages((state) => state.threads[conversationId]);
  const loadOlder = useMessages((state) => state.loadOlder);
  const retry = useMessages((state) => state.retry);
  const markRead = useMessages((state) => state.markRead);

  const scroller = useRef<HTMLDivElement>(null);
  const restoreFromBottom = useRef<number | null>(null); // scroll offset to keep while older messages load
  const positioned = useRef(false);
  const lastCount = useRef(0);
  const [showJump, setShowJump] = useState(false);

  const items = useMemo(() => thread?.items ?? [], [thread]);
  const rows = useMemo(() => buildRows(items, myId, lastReadAtOpen), [items, myId, lastReadAtOpen]);

  // Scroll position: first render -> unread divider or bottom; older page -> keep place;
  // new message at the bottom (e.g. mine) -> follow it.
  useLayoutEffect(() => {
    const element = scroller.current;
    if (!element || !thread?.loaded) return;
    if (!positioned.current) {
      positioned.current = true;
      const divider = element.querySelector<HTMLElement>("[data-unread-divider]");
      if (divider) element.scrollTop = divider.offsetTop - 80;
      else element.scrollTop = element.scrollHeight;
    } else if (restoreFromBottom.current !== null) {
      element.scrollTop = element.scrollHeight - restoreFromBottom.current;
      restoreFromBottom.current = null;
    } else if (items.length > lastCount.current) {
      element.scrollTop = element.scrollHeight;
    }
    lastCount.current = items.length;
  }, [items, thread?.loaded]);

  function handleScroll() {
    const element = scroller.current;
    if (!element || !thread) return;
    const fromBottom = element.scrollHeight - element.scrollTop - element.clientHeight;
    setShowJump(fromBottom > JUMP_BUTTON_THRESHOLD_PX);
    if (element.scrollTop < LOAD_OLDER_THRESHOLD_PX && thread.nextCursor !== null && !thread.loadingOlder) {
      restoreFromBottom.current = element.scrollHeight - element.scrollTop;
      void loadOlder(conversationId);
    }
  }

  // Read receipts: report the newest incoming message that has been on screen.
  const reportedUpTo = useRef(lastReadAtOpen);
  const seenUpTo = useRef(lastReadAtOpen);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flushRead = useCallback(() => {
    if (document.visibilityState !== "visible" || seenUpTo.current <= reportedUpTo.current) return;
    reportedUpTo.current = seenUpTo.current;
    markRead(conversationId, seenUpTo.current).catch(() => {
      reportedUpTo.current = lastReadAtOpen; // try again on the next sighting
    });
  }, [conversationId, lastReadAtOpen, markRead]);

  useEffect(() => {
    const root = scroller.current;
    if (!root) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const id = Number((entry.target as HTMLElement).dataset.messageId);
          if (entry.isIntersecting && id > seenUpTo.current) seenUpTo.current = id;
        }
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(flushRead, READ_DEBOUNCE_MS);
      },
      { root, threshold: 0.6 },
    );
    root.querySelectorAll("[data-message-id]").forEach((element) => observer.observe(element));
    const onVisible = () => flushRead();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      observer.disconnect();
      document.removeEventListener("visibilitychange", onVisible);
      if (timer.current) clearTimeout(timer.current);
    };
  }, [rows, flushRead]);

  return (
    <div className="relative min-h-0 flex-1">
      <div ref={scroller} onScroll={handleScroll} className="h-full overflow-y-auto px-4 pb-4" aria-label="Messages" role="log">
        {thread?.loaded && thread.nextCursor === null && <ConversationHero conversation={conversation} />}
        {thread?.loadingOlder && <p className="py-3 text-center text-xs text-text-muted">Loading…</p>}
        {rows.map((row) => {
          switch (row.kind) {
            case "date":
              return <DateSeparator key={row.key} label={row.label} />;
            case "unread":
              return <UnreadDivider key={row.key} count={row.count} />;
            case "system":
              return <SystemMessage key={row.key} text={row.message.text} />;
            case "message":
              return (
                <MessageBubble
                  key={row.key}
                  message={row.message}
                  mine={row.mine}
                  first={row.first}
                  last={row.last}
                  isGroup={conversation.type === "group"}
                  onRetry={(clientId) => void retry(conversationId, clientId)}
                />
              );
          }
        })}
      </div>
      {showJump && (
        <button
          type="button"
          aria-label="Scroll to bottom"
          onClick={() => scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" })}
          className="absolute right-6 bottom-4 flex h-9 w-9 items-center justify-center rounded-full border border-border-card bg-card text-text-primary shadow-md"
        >
          <ArrowDown size={18} aria-hidden />
        </button>
      )}
    </div>
  );
}
