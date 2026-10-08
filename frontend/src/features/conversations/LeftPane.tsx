"use client";

import { useLeftPane } from "@/store/left-pane";

import { ArchivePanel } from "./ArchivePanel";
import { ChatListPanel } from "./ChatListPanel";
import { ComposePanel } from "./ComposePanel";
import { NewGroupPanel } from "@/features/groups/NewGroupPanel";

import { FindByPhonePanel, FindByUsernamePanel } from "./FindPanels";

const PANELS = {
  chats: ChatListPanel,
  archive: ArchivePanel,
  compose: ComposePanel,
  findUsername: FindByUsernamePanel,
  findPhone: FindByPhonePanel,
  newGroup: NewGroupPanel,
} as const;

/** The left column of the Chats section; Signal swaps its content in place. */
export function LeftPane() {
  const mode = useLeftPane((state) => state.mode);
  const Panel = PANELS[mode];
  return (
    <aside className="flex w-full shrink-0 flex-col border-border bg-sidebar pane:w-[var(--sidebar-width)] pane:border-r">
      <Panel />
    </aside>
  );
}
