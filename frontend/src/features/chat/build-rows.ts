import { formatDaySeparator, isSameLocalDay } from "@/lib/format-time";
import type { ChatMessage } from "@/types/message";

export type TimelineRow =
  | { kind: "date"; key: string; label: string }
  | { kind: "unread"; key: string; count: number }
  | { kind: "system"; key: string; message: ChatMessage }
  | { kind: "message"; key: string; message: ChatMessage; mine: boolean; first: boolean; last: boolean };

const CLUSTER_GAP_MS = 3 * 60_000;

function key(message: ChatMessage): string {
  return message.client_id ?? String(message.id);
}

/**
 * Turns messages into rows: date separators, the unread divider (before the first incoming
 * message after `lastReadId`), system lines, and bubbles grouped into runs from the same
 * sender (same day, < 3 min apart, nothing in between).
 */
export function buildRows(messages: ChatMessage[], myId: number, lastReadId: number): TimelineRow[] {
  const isUnread = (m: ChatMessage) => m.id > lastReadId && m.kind === "text" && m.sender_id !== myId;
  const unreadCount = messages.filter(isUnread).length;
  const rows: TimelineRow[] = [];
  let dividerPlaced = false;

  messages.forEach((message, index) => {
    const previous = messages[index - 1];
    if (!previous || !isSameLocalDay(previous.created_at, message.created_at)) {
      rows.push({ kind: "date", key: `date-${message.created_at}`, label: formatDaySeparator(message.created_at) });
    }
    if (!dividerPlaced && unreadCount > 0 && isUnread(message)) {
      rows.push({ kind: "unread", key: "unread", count: unreadCount });
      dividerPlaced = true;
    }
    if (message.kind === "system") {
      rows.push({ kind: "system", key: key(message), message });
      return;
    }
    rows.push({ kind: "message", key: key(message), message, mine: message.sender_id === myId, first: true, last: true });
  });

  // Second pass: mark run boundaries between adjacent bubble rows.
  for (let i = 1; i < rows.length; i++) {
    const before = rows[i - 1];
    const current = rows[i];
    if (before?.kind !== "message" || current?.kind !== "message") continue;
    const sameRun =
      before.message.sender_id === current.message.sender_id &&
      new Date(current.message.created_at).getTime() - new Date(before.message.created_at).getTime() < CLUSTER_GAP_MS;
    if (sameRun) {
      before.last = false;
      current.first = false;
    }
  }
  return rows;
}
