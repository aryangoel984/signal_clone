"use client";

import { useEffect } from "react";

import { config } from "@/lib/config";
import { getToken } from "@/lib/session-storage";
import { RealtimeClient, setActiveRealtimeClient } from "@/lib/ws";
import { useAuthStore } from "@/store/auth";
import { useConversations } from "@/store/conversations";
import { useMessages } from "@/store/messages";
import { usePresenceStore } from "@/store/presence";
import { useRevisions } from "@/store/revisions";
import { useSettings } from "@/store/settings";
import { showToast } from "@/store/toasts";
import { useTyping } from "@/store/typing";
import type { Message } from "@/types/message";
import type { ServerEvent } from "@/types/realtime";

/** In-app notice for a message in a chat that isn't open; skipped for my own messages,
 *  system lines, muted chats, or when notifications are off in Settings. */
function notifyIfElsewhere(message: Message): void {
  const myId = useAuthStore.getState().user?.id;
  const notificationsOn = useSettings.getState().settings?.notifications_enabled ?? true;
  if (message.kind !== "text" || message.sender_id === myId || !notificationsOn) return;
  if (window.location.pathname === `/chats/${message.conversation_id}`) return;
  const chat = useConversations.getState().chats?.find((c) => c.id === message.conversation_id);
  if (chat?.muted_until && new Date(chat.muted_until) > new Date()) return;
  const sender = message.sender_name ?? "New message";
  const where = chat && chat.type === "group" ? `${sender} in ${chat.title}` : sender;
  showToast(`${where}: ${message.text}`, `/chats/${message.conversation_id}`);
}

function handle(event: ServerEvent): void {
  switch (event.type) {
    case "message.new": {
      const { message } = event.payload;
      useMessages.getState().receive(message);
      notifyIfElsewhere(message);
      if (message.sender_id !== null) useTyping.getState().stop(message.conversation_id, message.sender_id);
      useConversations.getState().refreshSoon();
      break;
    }
    case "message.status":
      useMessages.getState().applyStatuses(event.payload.conversation_id, event.payload.updates);
      useConversations.getState().refreshSoon();
      break;
    case "typing.start":
      useTyping.getState().start(event.payload.conversation_id, event.payload.user_id);
      break;
    case "typing.stop":
      useTyping.getState().stop(event.payload.conversation_id, event.payload.user_id);
      break;
    case "presence.update":
      usePresenceStore.getState().update(event.payload.user_id, {
        online: event.payload.online,
        lastSeenAt: event.payload.last_seen_at,
      });
      break;
    case "group.updated":
      useRevisions.getState().bump(event.payload.conversation_id);
      useConversations.getState().refreshSoon();
      break;
    case "message.deleted":
      useMessages.getState().applyDeleted(event.payload.conversation_id, event.payload.message_id);
      useConversations.getState().refreshSoon();
      break;
    case "reaction.updated": {
      const { conversation_id, message_id, user_id, emoji } = event.payload;
      useMessages.getState().applyReaction(conversation_id, message_id, user_id, emoji);
      break;
    }
    case "error":
    case "pong":
      break;
  }
}

/** After a dropped connection: refetch the chat list and anything newer in open chats. */
function catchUp(): void {
  useConversations.getState().refreshSoon();
  const { threads, catchUp: fetchNewer } = useMessages.getState();
  for (const id of Object.keys(threads)) void fetchNewer(Number(id)).catch(() => undefined);
}

/** Keeps one WebSocket open while signed in (mounted once in the app shell). */
export function useRealtime(): void {
  const status = useAuthStore((state) => state.status);

  useEffect(() => {
    const token = getToken();
    if (status !== "ready" || !token) return;
    const client = new RealtimeClient(config.wsUrl, token, {
      onEvent: handle,
      onReconnect: catchUp,
      onUnauthorized: () => void useAuthStore.getState().signOut(),
    });
    setActiveRealtimeClient(client);
    client.start();
    return () => {
      client.stop();
      setActiveRealtimeClient(null);
    };
  }, [status]);
}
