"use client";

import { Archive, ArchiveRestore, Ellipsis, Phone, Pin, PinOff, Search, UserRoundPlus, Video } from "lucide-react";
import { useState } from "react";

import { Avatar } from "@/components/Avatar";
import { IconButton } from "@/components/IconButton";
import { belowElement, Menu, type MenuItem, type MenuPosition } from "@/components/Menu";
import { ApiError, apiRequest } from "@/lib/api";
import { formatLastSeen } from "@/lib/format-time";
import { useConversations } from "@/store/conversations";
import { usePresence } from "@/store/presence";
import { COMING_SOON, showToast } from "@/store/toasts";
import type { ConversationDetail } from "@/types/conversation";

type ChatHeaderProps = {
  conversation: ConversationDetail;
  onChanged: (conversation: ConversationDetail) => void;
};

export function ChatHeader({ conversation, onChanged }: ChatHeaderProps) {
  const setPreferences = useConversations((state) => state.setPreferences);
  const loadChats = useConversations((state) => state.loadChats);
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null);
  const isGroup = conversation.type === "group";
  const presence = usePresence(conversation.other_user_id, {
    online: conversation.other_user_online ?? false,
    lastSeenAt: conversation.other_user_last_seen_at,
  });
  const subtitle = isGroup ? null : presence.online ? "Online" : formatLastSeen(presence.lastSeenAt);

  async function run(action: () => Promise<ConversationDetail>, done: string) {
    try {
      onChanged(await action());
      showToast(done);
    } catch (error) {
      showToast(error instanceof ApiError ? error.detail : "Something went wrong");
    }
  }

  const addToContacts = () =>
    run(async () => {
      await apiRequest("/contacts", { method: "POST", body: { user_id: conversation.other_user_id } });
      await loadChats();
      return apiRequest<ConversationDetail>(`/conversations/${conversation.id}`);
    }, "Added to contacts");

  const items: MenuItem[] = [
    ...(!isGroup && conversation.is_contact === false
      ? [{ label: "Add to contacts", icon: UserRoundPlus, onSelect: () => void addToContacts() }]
      : []),
    conversation.is_pinned
      ? { label: "Unpin chat", icon: PinOff, onSelect: () => void run(() => setPreferences(conversation.id, { is_pinned: false }), "Chat unpinned") }
      : { label: "Pin chat", icon: Pin, onSelect: () => void run(() => setPreferences(conversation.id, { is_pinned: true }), "Chat pinned") },
    conversation.is_archived
      ? {
          label: "Unarchive",
          icon: ArchiveRestore,
          onSelect: () => void run(() => setPreferences(conversation.id, { is_archived: false }), "Chat unarchived"),
        }
      : { label: "Archive", icon: Archive, onSelect: () => void run(() => setPreferences(conversation.id, { is_archived: true }), "Chat archived") },
  ];

  return (
    <header className="relative z-10 flex h-[52px] shrink-0 items-center gap-3 bg-chat px-4 shadow-[0_2px_10px_var(--header-shadow)]">
      <Avatar name={conversation.title} color={conversation.avatar_color} imageUrl={conversation.avatar_url} size={32} isGroup={isGroup} />
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-sm font-semibold text-text-primary">{conversation.title}</h1>
        {subtitle && <p className="truncate text-xs text-text-secondary">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-2">
        <IconButton icon={Video} label="Video call" onClick={() => showToast(COMING_SOON)} />
        {!isGroup && <IconButton icon={Phone} label="Voice call" onClick={() => showToast(COMING_SOON)} />}
        <IconButton icon={Search} label="Search in chat" onClick={() => showToast(COMING_SOON)} />
        <IconButton icon={Ellipsis} label="More options" onClick={(event) => setMenuPosition(belowElement(event.currentTarget))} />
      </div>
      {menuPosition && (
        <Menu
          items={items}
          onClose={() => setMenuPosition(null)}
          position={{ top: menuPosition.top, left: menuPosition.left - 200 }}
        />
      )}
    </header>
  );
}
