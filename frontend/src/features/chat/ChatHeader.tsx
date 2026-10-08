"use client";

import { Archive, ArchiveRestore, Ban, Bell, BellOff, ChevronLeft, Ellipsis, Phone, Pin, PinOff, Search, Settings, UserRoundPlus, Video } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Avatar } from "@/components/Avatar";
import { IconButton } from "@/components/IconButton";
import { belowElement, Menu, type MenuItem, type MenuPosition } from "@/components/Menu";
import { ConfirmDialog } from "@/components/Modal";
import { ApiError, apiRequest } from "@/lib/api";
import { formatLastSeen } from "@/lib/format-time";
import { useConversations } from "@/store/conversations";
import { usePresence } from "@/store/presence";
import { COMING_SOON, showToast } from "@/store/toasts";
import type { ConversationDetail } from "@/types/conversation";

// "Always" is stored as a far-future time, so the same muted_until check covers every option.
const MUTE_ALWAYS = "9999-12-31T00:00:00Z";

type ChatHeaderProps = {
  conversation: ConversationDetail;
  onChanged: (conversation: ConversationDetail) => void;
  onOpenSettings: () => void; // groups: the Group settings view
};

export function ChatHeader({ conversation, onChanged, onOpenSettings }: ChatHeaderProps) {
  const setPreferences = useConversations((state) => state.setPreferences);
  const loadChats = useConversations((state) => state.loadChats);
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null);
  const [confirmBlock, setConfirmBlock] = useState(false);
  const [muteMenu, setMuteMenu] = useState<MenuPosition | null>(null);
  const muted = conversation.muted_until !== null && new Date(conversation.muted_until) > new Date();
  const isGroup = conversation.type === "group";
  const presence = usePresence(conversation.other_user_id, {
    online: conversation.other_user_online ?? false,
    lastSeenAt: conversation.other_user_last_seen_at,
  });
  const subtitle = isGroup ? null : presence.online ? "Online" : formatLastSeen(presence.lastSeenAt);

  async function run(action: () => Promise<ConversationDetail>, done: string): Promise<void> {
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

  const setBlocked = (block: boolean) =>
    run(async () => {
      await apiRequest<void>(`/blocks/${conversation.other_user_id}`, { method: block ? "PUT" : "DELETE" });
      await loadChats();
      return apiRequest<ConversationDetail>(`/conversations/${conversation.id}`);
    }, block ? "Blocked" : "Unblocked");

  const mute = (until: string | null, done: string) =>
    void run(() => setPreferences(conversation.id, { muted_until: until }), done);
  const muteOptions: MenuItem[] = [
    { label: "Mute for 1 hour", onSelect: () => mute(new Date(Date.now() + 3600e3).toISOString(), "Muted for 1 hour") },
    { label: "Mute for 8 hours", onSelect: () => mute(new Date(Date.now() + 8 * 3600e3).toISOString(), "Muted for 8 hours") },
    { label: "Mute for 1 week", onSelect: () => mute(new Date(Date.now() + 7 * 24 * 3600e3).toISOString(), "Muted for 1 week") },
    { label: "Mute always", onSelect: () => mute(MUTE_ALWAYS, "Muted") },
  ];

  const items: MenuItem[] = [
    muted
      ? { label: "Unmute", icon: Bell, onSelect: () => mute(null, "Unmuted") }
      : { label: "Mute notifications…", icon: BellOff, onSelect: () => menuPosition && setMuteMenu(menuPosition) },
    ...(isGroup ? [{ label: "Group settings", icon: Settings, onSelect: onOpenSettings }] : []),
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
    ...(!isGroup && conversation.other_user_id !== null
      ? [
          conversation.blocked_by_me
            ? { label: "Unblock", icon: Ban, onSelect: () => void setBlocked(false) }
            : { label: "Block", icon: Ban, danger: true, onSelect: () => setConfirmBlock(true) },
        ]
      : []),
  ];

  return (
    <header className="relative z-10 flex h-[52px] shrink-0 items-center gap-3 bg-chat px-2 shadow-[0_2px_10px_var(--header-shadow)] pane:px-4">
      <Link href="/chats" aria-label="Back to chats" className="rounded-control p-1.5 text-text-primary hover:bg-selected pane:hidden">
        <ChevronLeft size={22} aria-hidden />
      </Link>
      <Avatar name={conversation.title} color={conversation.avatar_color} imageUrl={conversation.avatar_url} size={32} isGroup={isGroup} />
      <div className="min-w-0 flex-1">
        {isGroup ? (
          <h1 className="truncate text-sm font-semibold text-text-primary">
            <button type="button" onClick={onOpenSettings} className="hover:underline" title="Group settings">
              {conversation.title}
            </button>
          </h1>
        ) : (
          <h1 className="truncate text-sm font-semibold text-text-primary">{conversation.title}</h1>
        )}
        {subtitle && <p className="truncate text-xs text-text-secondary">{subtitle}</p>}
      </div>
      {muted && <BellOff size={15} className="shrink-0 text-text-secondary" aria-label="Muted" />}
      <div className="flex items-center gap-0.5 pane:gap-2">
        <IconButton icon={Video} label="Video call" onClick={() => showToast(COMING_SOON)} />
        {!isGroup && <IconButton icon={Phone} label="Voice call" onClick={() => showToast(COMING_SOON)} />}
        <IconButton icon={Search} label="Search in chat" onClick={() => showToast(COMING_SOON)} />
        <IconButton icon={Ellipsis} label="More options" onClick={(event) => setMenuPosition(belowElement(event.currentTarget))} />
      </div>
      {confirmBlock && (
        <ConfirmDialog
          title={`Block ${conversation.title}?`}
          message="Blocked people won't be able to call you or send you messages. In groups you share, you won't see their messages or changes."
          confirmLabel="Block"
          danger
          onCancel={() => setConfirmBlock(false)}
          onConfirm={() => {
            setConfirmBlock(false);
            void setBlocked(true);
          }}
        />
      )}
      {muteMenu && (
        <Menu items={muteOptions} onClose={() => setMuteMenu(null)} position={{ top: muteMenu.top, left: muteMenu.left - 200 }} />
      )}
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
