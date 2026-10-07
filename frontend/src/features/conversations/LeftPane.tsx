"use client";

import { useLeftPane } from "@/store/left-pane";

import { ArchivePanel } from "./ArchivePanel";
import { ChatListPanel } from "./ChatListPanel";
import { ComposePanel } from "./ComposePanel";
import { FindByPhonePanel, FindByUsernamePanel } from "./FindPanels";

const PANELS = {
  chats: ChatListPanel,
  archive: ArchivePanel,
  compose: ComposePanel,
  findUsername: FindByUsernamePanel,
  findPhone: FindByPhonePanel,
} as const;

/** The left column of the Chats section; Signal swaps its content in place. */
export function LeftPane() {
  const mode = useLeftPane((state) => state.mode);
  const Panel = PANELS[mode];
  return (
    <aside className="flex w-[var(--sidebar-width)] shrink-0 flex-col border-r border-border bg-sidebar">
      <Panel />
    </aside>
  );
}
