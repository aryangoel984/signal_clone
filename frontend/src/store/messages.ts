import { create } from "zustand";

import { ApiError, apiRequest } from "@/lib/api";
import { useConversations } from "@/store/conversations";
import type { MessageStatus } from "@/types/conversation";
import { type ChatMessage, DELETED_TEXT, type Message, type MessagePage, type Quote, type ReactionEmoji } from "@/types/message";

type Thread = {
  items: ChatMessage[]; // oldest first; my unconfirmed messages are at the end
  nextCursor: number | null;
  loaded: boolean;
  loadingOlder: boolean;
};

type MessagesState = {
  threads: Record<number, Thread>;
  loadLatest: (conversationId: number) => Promise<void>;
  loadOlder: (conversationId: number) => Promise<void>;
  send: (
    conversationId: number,
    text: string,
    me: { id: number; avatar_color: string },
    replyTo: ChatMessage | null,
  ) => Promise<void>;
  retry: (conversationId: number, clientId: string) => Promise<void>;
  markRead: (conversationId: number, upToMessageId: number) => Promise<void>;
  /** A message pushed over the WebSocket (from anyone, including my other tabs). */
  receive: (message: Message) => void;
  /** Tick updates for my messages; statuses only ever move forward. */
  applyStatuses: (conversationId: number, updates: { message_id: number; status: MessageStatus }[]) => void;
  /** Sets (emoji) or removes (null) my reaction: shown at once, undone if the server refuses. */
  react: (conversationId: number, messageId: number, myId: number, emoji: ReactionEmoji | null) => Promise<void>;
  /** One user's reaction changed (reaction.updated, or my own optimistic change). */
  applyReaction: (conversationId: number, messageId: number, userId: number, emoji: string | null) => void;
  /** Deletes my message for everyone (the server checks sender and time window). */
  deleteForEveryone: (conversationId: number, messageId: number) => Promise<void>;
  /** A message became a tombstone (message.deleted, or my own delete): clear it and quotes of it. */
  applyDeleted: (conversationId: number, messageId: number) => void;
  /** After a reconnect: fetch everything newer than what's loaded. */
  catchUp: (conversationId: number) => Promise<void>;
};

const STATUS_RANK: Record<MessageStatus, number> = { sent: 1, delivered: 2, read: 3 };

const EMPTY: Thread = { items: [], nextCursor: null, loaded: false, loadingOlder: false };
const PAGE_SIZE = 50;

function newClientId(): string {
  return crypto.randomUUID();
}

/** The quote my optimistic reply shows until the server's copy replaces it. */
export function quoteOf(original: ChatMessage, myId: number): Quote {
  const authorName = original.sender_id === myId ? "You" : (original.sender_name ?? "");
  return { id: original.id, sender_id: original.sender_id, author_name: authorName, text: original.text };
}

/** The server's copy of a message, without letting it lower a status we already know is
 *  higher: the POST response ("sent") can arrive after live delivered/read events. */
function mergeConfirmed(existing: ChatMessage, incoming: Message): ChatMessage {
  const keep = existing.status && (!incoming.status || STATUS_RANK[existing.status] > STATUS_RANK[incoming.status]);
  return keep ? { ...incoming, status: existing.status } : incoming;
}

export const useMessages = create<MessagesState>()((set, get) => {
  const thread = (id: number): Thread => get().threads[id] ?? EMPTY;
  const update = (id: number, change: (current: Thread) => Partial<Thread>) =>
    set((state) => {
      const current = state.threads[id] ?? EMPTY;
      return { threads: { ...state.threads, [id]: { ...current, ...change(current) } } };
    });
  const replaceByClientId = (id: number, clientId: string, change: (message: ChatMessage) => ChatMessage) =>
    update(id, (current) => ({
      items: current.items.map((message) => (message.client_id === clientId ? change(message) : message)),
    }));

  async function post(conversationId: number, clientId: string, text: string, replyToId: number | null) {
    try {
      const saved = await apiRequest<Message>(`/conversations/${conversationId}/messages`, {
        method: "POST",
        body: { client_id: clientId, body: text, reply_to_id: replyToId },
      });
      replaceByClientId(conversationId, clientId, (existing) => mergeConfirmed(existing, saved));
      void useConversations.getState().loadChats(); // move the chat to the top with the new preview
    } catch (error) {
      // 4xx other than network/server trouble won't succeed on retry, but the user can still see it failed.
      if (error instanceof ApiError && error.status === 401) return;
      replaceByClientId(conversationId, clientId, (message) => ({ ...message, localStatus: "failed" }));
    }
  }

  return {
    threads: {},

    loadLatest: async (conversationId) => {
      const page = await apiRequest<MessagePage>(`/conversations/${conversationId}/messages?limit=${PAGE_SIZE}`);
      update(conversationId, (current) => ({
        // keep my still-unconfirmed messages after the fresh page
        items: [...page.items, ...current.items.filter((message) => message.localStatus)],
        nextCursor: page.next_cursor,
        loaded: true,
      }));
    },

    loadOlder: async (conversationId) => {
      const { nextCursor, loadingOlder } = thread(conversationId);
      if (nextCursor === null || loadingOlder) return;
      update(conversationId, () => ({ loadingOlder: true }));
      try {
        const page = await apiRequest<MessagePage>(
          `/conversations/${conversationId}/messages?limit=${PAGE_SIZE}&before=${nextCursor}`,
        );
        update(conversationId, (current) => ({
          items: [...page.items, ...current.items],
          nextCursor: page.next_cursor,
        }));
      } finally {
        update(conversationId, () => ({ loadingOlder: false }));
      }
    },

    /** Optimistic: the bubble appears at once with a clock, then becomes the server's copy. */
    send: async (conversationId, text, me, replyTo) => {
      const clientId = newClientId();
      const optimistic: ChatMessage = {
        id: -Date.now(),
        conversation_id: conversationId,
        client_id: clientId,
        kind: "text",
        text,
        sender_id: me.id,
        sender_name: null,
        sender_avatar_color: me.avatar_color,
        sender_avatar_url: null,
        created_at: new Date().toISOString(),
        status: null,
        deleted: false,
        reply_to_id: replyTo?.id ?? null,
        quote: replyTo ? quoteOf(replyTo, me.id) : null,
        reactions: [],
        localStatus: "sending",
      };
      update(conversationId, (current) => ({ items: [...current.items, optimistic] }));
      await post(conversationId, clientId, text, optimistic.reply_to_id);
    },

    /** Resends with the same client_id, so the server can't create a duplicate. */
    retry: async (conversationId, clientId) => {
      const message = thread(conversationId).items.find((item) => item.client_id === clientId);
      if (!message) return;
      replaceByClientId(conversationId, clientId, (item) => ({ ...item, localStatus: "sending" }));
      await post(conversationId, clientId, message.text, message.reply_to_id);
    },

    markRead: async (conversationId, upToMessageId) => {
      await apiRequest<void>(`/conversations/${conversationId}/read`, {
        method: "POST",
        body: { up_to_message_id: upToMessageId },
      });
      void useConversations.getState().loadChats();
    },

    receive: (message) => {
      const current = get().threads[message.conversation_id];
      if (!current?.loaded) return; // not open yet: it'll be in the next fetch
      update(message.conversation_id, (thread) => {
        const byId = thread.items.findIndex((item) => item.id === message.id);
        const byClientId = message.client_id
          ? thread.items.findIndex((item) => item.client_id === message.client_id)
          : -1;
        const index = byId >= 0 ? byId : byClientId;
        if (index < 0) return { items: [...thread.items, message] };
        const items = [...thread.items];
        items[index] = mergeConfirmed(items[index] as ChatMessage, message);
        return { items };
      });
    },

    applyStatuses: (conversationId, updates) => {
      const statuses = new Map(updates.map((u) => [u.message_id, u.status]));
      update(conversationId, (thread) => ({
        items: thread.items.map((item) => {
          const next = statuses.get(item.id);
          const forward = next && (!item.status || STATUS_RANK[next] > STATUS_RANK[item.status]);
          return forward ? { ...item, status: next } : item;
        }),
      }));
    },

    react: async (conversationId, messageId, myId, emoji) => {
      const message = thread(conversationId).items.find((item) => item.id === messageId);
      const previous = message?.reactions.find((reaction) => reaction.user_id === myId)?.emoji ?? null;
      get().applyReaction(conversationId, messageId, myId, emoji);
      try {
        await apiRequest<void>(`/messages/${messageId}/reaction`, emoji === null ? { method: "DELETE" } : { method: "PUT", body: { emoji } });
      } catch (error) {
        get().applyReaction(conversationId, messageId, myId, previous);
        throw error;
      }
    },

    applyReaction: (conversationId, messageId, userId, emoji) => {
      update(conversationId, (current) => ({
        items: current.items.map((item) => {
          if (item.id !== messageId) return item;
          const others = item.reactions.filter((reaction) => reaction.user_id !== userId);
          const mine = item.reactions.find((reaction) => reaction.user_id === userId);
          if (emoji === null) return { ...item, reactions: others };
          // A changed reaction keeps its place (the server updates the row, created_at stays).
          if (mine) return { ...item, reactions: item.reactions.map((r) => (r.user_id === userId ? { ...r, emoji } : r)) };
          return { ...item, reactions: [...others, { user_id: userId, emoji }] };
        }),
      }));
    },

    deleteForEveryone: async (conversationId, messageId) => {
      await apiRequest<void>(`/messages/${messageId}`, { method: "DELETE" });
      get().applyDeleted(conversationId, messageId);
      void useConversations.getState().loadChats(); // the preview may now be the tombstone
    },

    applyDeleted: (conversationId, messageId) => {
      update(conversationId, (current) => ({
        items: current.items.map((item) => {
          if (item.id === messageId) {
            return { ...item, deleted: true, text: DELETED_TEXT, status: null, reply_to_id: null, quote: null, reactions: [] };
          }
          // Replies to it keep reply_to_id but lose the quote: "Original message not found".
          return item.quote?.id === messageId ? { ...item, quote: null } : item;
        }),
      }));
    },

    catchUp: async (conversationId) => {
      const confirmed = thread(conversationId).items.filter((item) => item.id > 0);
      const lastId = confirmed.at(-1)?.id;
      if (lastId === undefined) return;
      const page = await apiRequest<MessagePage>(`/conversations/${conversationId}/messages?after=${lastId}&limit=100`);
      page.items.forEach((message) => get().receive(message));
    },
  };
});
