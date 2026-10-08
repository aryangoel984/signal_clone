"use client";

import { useSelectedLayoutSegment } from "next/navigation";

import { LeftPane } from "@/features/conversations/LeftPane";

/** Two panes from 900px. Below that, one pane: the list at /chats, the chat at /chats/[id]. */
export default function ChatsLayout({ children }: LayoutProps<"/chats">) {
  const chatOpen = useSelectedLayoutSegment() !== null;
  return (
    <>
      <div className={`${chatOpen ? "hidden" : "flex"} min-w-0 flex-1 pane:flex pane:flex-none`}>
        <LeftPane />
      </div>
      <main className={`${chatOpen ? "flex" : "hidden"} min-w-0 flex-1 pane:flex`}>{children}</main>
    </>
  );
}
