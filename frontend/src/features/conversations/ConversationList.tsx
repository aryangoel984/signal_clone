"use client";

import { Archive, ArchiveRestore, CheckCheck, Pin, PinOff } from "lucide-react";
import { usePathname } from "next/navigation";
import { type MouseEvent, useState } from "react";

import { Menu, type MenuPosition } from "@/components/Menu";
import { ApiError } from "@/lib/api";
import { useConversations } from "@/store/conversations";
import { useMessages } from "@/store/messages";
import { showToast } from "@/store/toasts";
import type { ConversationSummary } from "@/types/conversation";

import { ConversationListItem } from "./ConversationListItem";

type ConversationListProps = {
  chats: ConversationSummary[];
  emptyText?: string;
};

export function ConversationList({ chats, emptyText }: ConversationListProps) {
  const pathname = usePathname();
  const setPreferences = useConversations((state) => state.setPreferences);
  const markRead = useMessages((state) => state.markRead);
  const [menu, setMenu] = useState<{ chat: ConversationSummary; position: MenuPosition } | null>(null);

  function openMenu(event: MouseEvent, chat: ConversationSummary) {
    event.preventDefault();
    setMenu({ chat, position: { top: event.clientY, left: event.clientX } });
  }

  function update(chat: ConversationSummary, changes: Parameters<typeof setPreferences>[1], done: string) {
    setPreferences(chat.id, changes)
      .then(() => showToast(done))
      .catch((error: unknown) => showToast(error instanceof ApiError ? error.detail : "Something went wrong"));
  }

  if (chats.length === 0 && emptyText) {
    return <p className="px-4 py-6 text-center text-sm text-text-secondary">{emptyText}</p>;
  }

  return (
    <>
      <ul className="flex flex-col px-3 pb-3">
        {chats.map((chat) => (
          <ConversationListItem
            key={chat.id}
            chat={chat}
            selected={pathname === `/chats/${chat.id}`}
            onContextMenu={openMenu}
          />
        ))}
      </ul>
      {menu && (
        <Menu
          position={menu.position}
          onClose={() => setMenu(null)}
          items={[
            ...(menu.chat.unread_count > 0 && menu.chat.last_message
              ? [
                  {
                    label: "Mark as read",
                    icon: CheckCheck,
                    onSelect: () => {
                      const lastId = menu.chat.last_message?.id;
                      if (lastId) markRead(menu.chat.id, lastId).catch(() => showToast("Something went wrong"));
                    },
                  },
                ]
              : []),
            menu.chat.is_pinned
              ? { label: "Unpin chat", icon: PinOff, onSelect: () => update(menu.chat, { is_pinned: false }, "Chat unpinned") }
              : { label: "Pin chat", icon: Pin, onSelect: () => update(menu.chat, { is_pinned: true }, "Chat pinned") },
            menu.chat.is_archived
              ? {
                  label: "Unarchive",
                  icon: ArchiveRestore,
                  onSelect: () => update(menu.chat, { is_archived: false }, "Chat unarchived"),
                }
              : { label: "Archive", icon: Archive, onSelect: () => update(menu.chat, { is_archived: true }, "Chat archived") },
          ]}
        />
      )}
    </>
  );
}
