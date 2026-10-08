"use client";

import type { ReactNode } from "react";

type SectionPlaceholderProps = {
  title: string;
  actions?: ReactNode; // header buttons
  sidebar?: ReactNode;
  emptyState: ReactNode; // main pane
};

/** Two-pane layout for the mocked sections (Calls, Stories, references 8.50.51 / 8.50.54).
 *  Below 900px only the left column shows. */
export function SectionPlaceholder({ title, actions, sidebar, emptyState }: SectionPlaceholderProps) {
  return (
    <>
      <aside className="flex w-full shrink-0 flex-col border-border bg-sidebar pane:w-[var(--sidebar-width)] pane:border-r">
        <header className="flex h-[52px] shrink-0 items-center gap-1 pr-3 pl-4">
          <h1 className="flex-1 text-xl font-semibold text-text-primary">{title}</h1>
          {actions}
        </header>
        {sidebar}
      </aside>
      <main className="hidden flex-1 flex-col items-center justify-center gap-3 bg-chat text-text-secondary pane:flex">{emptyState}</main>
    </>
  );
}
