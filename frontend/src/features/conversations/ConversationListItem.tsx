"use client";

import { BellOff, Pin } from "lucide-react";
import Link from "next/link";
import type { MouseEvent } from "react";

import { Avatar } from "@/components/Avatar";
import { PresenceDot } from "@/components/PresenceDot";
import { StatusTicks } from "@/components/StatusTicks";
import { TypingDots } from "@/components/TypingDots";
import { UnreadBadge } from "@/components/UnreadBadge";
import { formatListTime } from "@/lib/format-time";
import { usePresence } from "@/store/presence";
import { useTypingIn } from "@/store/typing";
import type { ConversationSummary } from "@/types/conversation";

type ConversationListItemProps = {
  chat: ConversationSummary;
  selected: boolean;
  onContextMenu?: (event: MouseEvent, chat: ConversationSummary) => void;
};

function previewText(chat: ConversationSummary): string {
  const last = chat.last_message;
  if (!last) return "";
  if (last.kind === "system" || chat.type === "direct") return last.text;
  // Groups name the sender: "You: ..." or "Priya: ...".
  const sender = last.sender_name === null ? "You" : last.sender_name.split(" ")[0];
  return `${sender}: ${last.text}`;
}

function isMuted(chat: ConversationSummary): boolean {
  return chat.muted_until !== null && new Date(chat.muted_until) > new Date();
}

export function ConversationListItem({ chat, selected, onContextMenu }: ConversationListItemProps) {
  const unread = chat.unread_count > 0;
  const status = chat.last_message?.status;
  const someoneTyping = useTypingIn(chat.id).length > 0;
  const presence = usePresence(chat.other_user_id, {
    online: chat.other_user_online ?? false,
    lastSeenAt: chat.other_user_last_seen_at,
  });

  return (
    <li>
      <Link
        href={`/chats/${chat.id}`}
        aria-current={selected ? "page" : undefined}
        onContextMenu={(event) => onContextMenu?.(event, chat)}
        className={`flex items-center gap-3 rounded-lg px-3.5 py-3 transition-colors hover:bg-selected ${selected ? "bg-selected" : ""}`}
      >
        <span className="relative shrink-0">
          <Avatar
            name={chat.title}
            color={chat.avatar_color}
            imageUrl={chat.avatar_url}
            size={48}
            isGroup={chat.type === "group"}
          />
          {chat.type === "direct" && presence.online && <PresenceDot />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className={`truncate text-sm text-text-primary ${unread ? "font-bold" : "font-semibold"}`}>
              {chat.title}
            </span>
            {isMuted(chat) && <BellOff size={13} className="shrink-0 text-text-secondary" aria-label="Muted" />}
            <span className="ml-auto flex shrink-0 items-center gap-1 text-xs text-text-secondary">
              {chat.is_pinned && <Pin size={12} aria-label="Pinned" />}
              {chat.last_message && formatListTime(chat.last_message.created_at)}
            </span>
          </div>
          <div className="mt-0.5 flex items-center gap-2">
            {someoneTyping ? (
              <span className="flex h-5 items-center text-text-secondary">
                <TypingDots size={6} />
              </span>
            ) : (
              <span className={`truncate text-sm ${unread ? "font-medium text-text-primary" : "text-text-secondary"}`}>
                {previewText(chat)}
              </span>
            )}
            <span className="ml-auto flex shrink-0 items-center text-text-secondary">
              {unread ? <UnreadBadge count={chat.unread_count} /> : status && <StatusTicks status={status} />}
            </span>
          </div>
        </div>
      </Link>
    </li>
  );
}
