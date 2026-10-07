import { Users } from "lucide-react";

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

/** Full-width rule with "N Unread Messages", where the reader left off. */
export function UnreadDivider({ count }: { count: number }) {
  return (
    <div className="-mx-4 mt-6 mb-2 border-t border-border-card pt-1 text-center text-[13px] font-semibold text-text-primary" data-unread-divider>
      {count} Unread {count === 1 ? "Message" : "Messages"}
    </div>
  );
}
