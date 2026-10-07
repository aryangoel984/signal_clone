"use client";

import { useEffect } from "react";

import { useConversations } from "@/store/conversations";
import { useLeftPane } from "@/store/left-pane";
import { showToast } from "@/store/toasts";

import { ConversationList } from "./ConversationList";
import { PaneHeader } from "./PaneHeader";

export function ArchivePanel() {
  const archived = useConversations((state) => state.archived);
  const loadArchived = useConversations((state) => state.loadArchived);
  const setMode = useLeftPane((state) => state.setMode);

  useEffect(() => {
    loadArchived().catch(() => showToast("Couldn't load archived chats"));
  }, [loadArchived]);

  return (
    <>
      <PaneHeader title="Archived Chats" onBack={() => setMode("chats")} />
      <p className="px-4 pb-3 text-xs text-text-secondary">
        These chats are archived and will only appear in the Inbox if new messages are received.
      </p>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {archived && <ConversationList chats={archived} emptyText="No archived chats" />}
      </div>
    </>
  );
}
