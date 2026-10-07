import type { MessageStatus } from "@/types/conversation";

const LABELS: Record<MessageStatus | "sending", string> = {
  sending: "Sending",
  sent: "Sent",
  delivered: "Delivered",
  read: "Read",
};

/**
 * Signal's delivery marks: sent = one outlined check-circle, delivered = two outlined
 * overlapping circles, read = two filled circles. Drawn in currentColor.
 */
export function StatusTicks({ status, size = 16 }: { status: MessageStatus | "sending"; size?: number }) {
  const height = (size * 12) / 16;
  if (status === "sending") {
    return (
      <svg width={height} height={height} viewBox="0 0 12 12" role="img" aria-label={LABELS.sending}>
        <circle cx="6" cy="6" r="5" fill="none" stroke="currentColor" strokeWidth="1.2" />
        <path d="M6 3.2V6l1.8 1.2" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    );
  }
  const filled = status === "read";
  const circle = (cx: number) =>
    filled ? (
      <circle cx={cx} cy="6" r="5" fill="currentColor" />
    ) : (
      <circle cx={cx} cy="6" r="4.6" fill="none" stroke="currentColor" strokeWidth="1.2" />
    );
  const check = (offset: number) => (
    <path
      d={`M${3.4 + offset} 6.1l1.7 1.6 3.2-3.4`}
      fill="none"
      stroke={filled ? "var(--bg-sidebar)" : "currentColor"}
      strokeWidth="1.3"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  );
  return (
    <svg width={size} height={height} viewBox="0 0 16 12" role="img" aria-label={LABELS[status]}>
      {status !== "sent" && circle(5.5)}
      {circle(status === "sent" ? 8 : 10.5)}
      {check(status === "sent" ? 1.6 : 4.1)}
    </svg>
  );
}
