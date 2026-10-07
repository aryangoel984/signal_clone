import { create } from "zustand";

import { ApiError, apiRequest } from "@/lib/api";
import { useConversations } from "@/store/conversations";
import type { ChatMessage, Message, MessagePage } from "@/types/message";

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
  send: (conversationId: number, text: string, me: { id: number; avatar_color: string }) => Promise<void>;
  retry: (conversationId: number, clientId: string) => Promise<void>;
  markRead: (conversationId: number, upToMessageId: number) => Promise<void>;
};

const EMPTY: Thread = { items: [], nextCursor: null, loaded: false, loadingOlder: false };
const PAGE_SIZE = 50;

function newClientId(): string {
  return crypto.randomUUID();
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

  async function post(conversationId: number, clientId: string, text: string) {
    try {
      const saved = await apiRequest<Message>(`/conversations/${conversationId}/messages`, {
        method: "POST",
        body: { client_id: clientId, body: text },
      });
      replaceByClientId(conversationId, clientId, () => saved);
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
    send: async (conversationId, text, me) => {
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
        localStatus: "sending",
      };
      update(conversationId, (current) => ({ items: [...current.items, optimistic] }));
      await post(conversationId, clientId, text);
    },

    /** Resends with the same client_id, so the server can't create a duplicate. */
    retry: async (conversationId, clientId) => {
      const message = thread(conversationId).items.find((item) => item.client_id === clientId);
      if (!message) return;
      replaceByClientId(conversationId, clientId, (item) => ({ ...item, localStatus: "sending" }));
      await post(conversationId, clientId, message.text);
    },

    markRead: async (conversationId, upToMessageId) => {
      await apiRequest<void>(`/conversations/${conversationId}/read`, {
        method: "POST",
        body: { up_to_message_id: upToMessageId },
      });
      void useConversations.getState().loadChats();
    },
  };
});
