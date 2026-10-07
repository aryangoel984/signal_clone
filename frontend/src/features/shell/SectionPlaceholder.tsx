import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

type SectionPlaceholderProps = {
  title: string;
  icon: LucideIcon;
  message: string;
  sidebar?: ReactNode;
};

/** Two-pane "Coming soon" layout for sections that are mocked (Calls, Stories). */
export function SectionPlaceholder({ title, icon: Icon, message, sidebar }: SectionPlaceholderProps) {
  return (
    <>
      <aside className="flex w-[var(--sidebar-width)] shrink-0 flex-col border-r border-border bg-sidebar">
        <h1 className="px-4 pt-3.5 pb-3 text-xl font-semibold text-text-primary">{title}</h1>
        {sidebar ?? <p className="px-4 text-sm text-text-secondary">Coming soon</p>}
      </aside>
      <main className="flex flex-1 flex-col items-center justify-center gap-3 bg-chat text-text-secondary">
        <Icon size={28} strokeWidth={1.5} aria-hidden />
        <p className="text-sm">{message}</p>
      </main>
    </>
  );
}
