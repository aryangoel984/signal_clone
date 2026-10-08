"use client";

import { ArrowDown } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "@/lib/api";
import { useMessages } from "@/store/messages";
import { showToast } from "@/store/toasts";
import { useTypingIn } from "@/store/typing";
import type { ConversationDetail } from "@/types/conversation";
import type { ChatMessage, ReactionEmoji } from "@/types/message";

import { buildRows, unreadMarker } from "./build-rows";
import { ConversationHero } from "./ConversationHero";
import { MessageBubble } from "./MessageBubble";
import { MessageDetailsModal } from "./MessageDetailsModal";
import { DateSeparator, SystemMessage, UnreadDivider } from "./TimelineMarkers";
import { TypingIndicator } from "./TypingIndicator";

type TimelineProps = {
  conversation: ConversationDetail;
  myId: number;
  lastReadAtOpen: number; // frozen when the chat opened, so the divider doesn't jump while reading
  onReply: (message: ChatMessage) => void;
};

const LOAD_OLDER_THRESHOLD_PX = 200;
const JUMP_BUTTON_THRESHOLD_PX = 300;
const READ_DEBOUNCE_MS = 300;
const JUMP_MAX_STEPS = 40; // older pages / frames to wait while looking for a quoted message
const HIGHLIGHT_MS = 1500;

const nextFrame = () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));

export function Timeline({ conversation, myId, lastReadAtOpen, onReply }: TimelineProps) {
  const conversationId = conversation.id;
  const thread = useMessages((state) => state.threads[conversationId]);
  const loadOlder = useMessages((state) => state.loadOlder);
  const retry = useMessages((state) => state.retry);
  const markRead = useMessages((state) => state.markRead);
  const react = useMessages((state) => state.react);

  const scroller = useRef<HTMLDivElement>(null);
  const restoreFromBottom = useRef<number | null>(null); // scroll offset to keep while older messages load
  const positioned = useRef(false);
  const lastCount = useRef(0);
  const [showJump, setShowJump] = useState(false);
  const [detailsFor, setDetailsFor] = useState<number | null>(null);
  const [highlightId, setHighlightId] = useState<number | null>(null);
  const highlightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const items = useMemo(() => thread?.items ?? [], [thread]);
  const [marker] = useState(() => unreadMarker(items, myId, lastReadAtOpen)); // messages are loaded before mount
  const rows = useMemo(() => buildRows(items, myId, marker), [items, myId, marker]);
  const typingUserIds = useTypingIn(conversationId).filter((id) => id !== myId);
  const nearBottom = useRef(true);
  const NEAR_BOTTOM_PX = 150;

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
    } else if (items.length > lastCount.current || typingUserIds.length > 0) {
      // Follow new messages / typing only if the reader is already at the bottom, or it's mine.
      const newestIsMine = items.at(-1)?.sender_id === myId && items.length > lastCount.current;
      if (nearBottom.current || newestIsMine) element.scrollTop = element.scrollHeight;
    }
    lastCount.current = items.length;
  }, [items, thread?.loaded, typingUserIds.length, myId]);

  function handleScroll() {
    const element = scroller.current;
    if (!element || !thread) return;
    const fromBottom = element.scrollHeight - element.scrollTop - element.clientHeight;
    nearBottom.current = fromBottom < NEAR_BOTTOM_PX;
    setShowJump(fromBottom > JUMP_BUTTON_THRESHOLD_PX);
    if (element.scrollTop < LOAD_OLDER_THRESHOLD_PX && thread.nextCursor !== null && !thread.loadingOlder) {
      restoreFromBottom.current = element.scrollHeight - element.scrollTop;
      void loadOlder(conversationId);
    }
  }

  /** Scrolls to a quoted message, loading older pages until it's in the DOM, then flashes it. */
  async function jumpTo(messageId: number) {
    const element = () => scroller.current?.querySelector<HTMLElement>(`[data-bubble-id="${messageId}"]`);
    for (let step = 0; !element() && step < JUMP_MAX_STEPS; step++) {
      const current = useMessages.getState().threads[conversationId];
      if (!current || (current.nextCursor === null && !current.loadingOlder)) break; // nothing older left
      if (!current.loadingOlder && scroller.current) {
        restoreFromBottom.current = scroller.current.scrollHeight - scroller.current.scrollTop;
        await loadOlder(conversationId);
      }
      await nextFrame(); // let React render the new page
    }
    const target = element();
    if (!target) {
      showToast("Original message not found");
      return;
    }
    target.scrollIntoView({ block: "center", behavior: "smooth" });
    setHighlightId(messageId);
    if (highlightTimer.current) clearTimeout(highlightTimer.current);
    highlightTimer.current = setTimeout(() => setHighlightId(null), HIGHLIGHT_MS);
  }
  useEffect(() => () => {
    if (highlightTimer.current) clearTimeout(highlightTimer.current);
  }, []);

  function handleReact(messageId: number, emoji: ReactionEmoji | null) {
    react(conversationId, messageId, myId, emoji).catch((error: unknown) =>
      showToast(error instanceof ApiError ? error.detail : "Couldn't react"),
    );
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
                  myId={myId}
                  mine={row.mine}
                  first={row.first}
                  last={row.last}
                  isGroup={conversation.type === "group"}
                  onRetry={(clientId) => void retry(conversationId, clientId)}
                  onShowDetails={setDetailsFor}
                  highlighted={highlightId === row.message.id}
                  onReply={onReply}
                  onReact={handleReact}
                  onJumpTo={(id) => void jumpTo(id)}
                />
              );
          }
        })}
        {typingUserIds.length > 0 && (
          <TypingIndicator
            members={conversation.type === "group" ? conversation.members.filter((m) => typingUserIds.includes(m.user_id)) : []}
          />
        )}
      </div>
      {detailsFor !== null && <MessageDetailsModal messageId={detailsFor} onClose={() => setDetailsFor(null)} />}
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
