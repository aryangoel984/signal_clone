import { Lock, Users } from "lucide-react";

export function DateSeparator({ label }: { label: string }) {
  return <div className="mt-5 mb-1 text-center text-[13px] text-text-muted">{label}</div>;
}

export function SystemMessage({ text }: { text: string }) {
  return (
    <div className="my-3 flex items-center justify-center gap-2 text-[13px] text-text-muted">
      <Users size={15} strokeWidth={1.75} aria-hidden />
      <span>{text}</span>
    </div>
  );
}

/** Shown once at the start of every chat, under the intro card. The wording is Signal's own
 *  ("Messages and chat info are protected by end-to-end encryption"); here it's a visual
 *  placeholder, the app has no real encryption (see README). */
export function EncryptionNotice() {
  return (
    <div className="mx-auto mt-3 mb-1 flex max-w-[460px] items-center justify-center gap-1.5 text-center text-[13px] leading-[18px] text-text-muted">
      <Lock size={13} strokeWidth={2} className="shrink-0" aria-hidden />
      <span>Messages and chat info are protected by end-to-end encryption</span>
    </div>
  );
}

/** Full-width rule with "N Unread Messages", where the reader left off. */
export function UnreadDivider({ count }: { count: number }) {
  return (
    <div className="-mx-4 mt-6 mb-2 border-t border-border-card pt-1 text-center text-[13px] font-semibold text-text-primary" data-unread-divider>
      {count} Unread {count === 1 ? "Message" : "Messages"}
    </div>
  );
}
