const MINUTE = 60_000;

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/**
 * Chat-list timestamps, as Signal Desktop shows them:
 * "Now" (< 1 min), "5m" (< 1 h), "5:42 PM" (today), "Yesterday", "Mon" (this week),
 * "Oct 7" (this year), "Oct 7, 2025".
 */
export function formatListTime(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  const elapsed = now.getTime() - date.getTime();
  if (elapsed < MINUTE) return "Now";
  if (elapsed < 60 * MINUTE) return `${Math.floor(elapsed / MINUTE)}m`;
  if (isSameDay(date, now)) return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (isSameDay(date, yesterday)) return "Yesterday";
  if (elapsed < 7 * 24 * 60 * MINUTE) return date.toLocaleDateString(undefined, { weekday: "short" });
  if (date.getFullYear() === now.getFullYear()) {
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/** Inside a bubble: "Now", "5m" for the first hour, then the time of day. */
export function formatBubbleTime(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  const elapsed = now.getTime() - date.getTime();
  if (elapsed < MINUTE) return "Now";
  if (elapsed < 60 * MINUTE) return `${Math.floor(elapsed / MINUTE)}m`;
  return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

/** Date separator in the timeline: "Today", "Yesterday", "Monday", "Mon, Oct 5", "Oct 5, 2025". */
export function formatDaySeparator(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  if (isSameDay(date, now)) return "Today";
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (isSameDay(date, yesterday)) return "Yesterday";
  if (now.getTime() - date.getTime() < 7 * 24 * 60 * MINUTE) {
    return date.toLocaleDateString(undefined, { weekday: "long" });
  }
  if (date.getFullYear() === now.getFullYear()) {
    return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  }
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function isSameLocalDay(a: string, b: string): boolean {
  return isSameDay(new Date(a), new Date(b));
}

/** Chat header subtitle for someone offline: "Last seen 5m ago", "Last seen yesterday", ... */
export function formatLastSeen(iso: string | null, now: Date = new Date()): string {
  if (!iso) return "";
  const date = new Date(iso);
  const elapsed = now.getTime() - date.getTime();
  if (elapsed < MINUTE) return "Last seen just now";
  if (elapsed < 60 * MINUTE) return `Last seen ${Math.floor(elapsed / MINUTE)}m ago`;
  if (isSameDay(date, now)) return `Last seen today at ${date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (isSameDay(date, yesterday)) return "Last seen yesterday";
  return `Last seen ${date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
}
