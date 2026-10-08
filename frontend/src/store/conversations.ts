import { create } from "zustand";

import { apiRequest } from "@/lib/api";
import { usePresenceStore } from "@/store/presence";
import type { ConversationDetail, ConversationSummary, PreferenceChanges } from "@/types/conversation";

type ConversationsState = {
  chats: ConversationSummary[] | null; // null until first load
  archived: ConversationSummary[] | null;
  loadChats: () => Promise<void>;
  loadArchived: () => Promise<void>;
  setPreferences: (conversationId: number, changes: PreferenceChanges) => Promise<ConversationDetail>;
  openDirect: (userId: number) => Promise<ConversationDetail>;
  /** Debounced reload for bursts of realtime events. */
  refreshSoon: () => void;
};

const REFRESH_DEBOUNCE_MS = 150;
let refreshTimer: ReturnType<typeof setTimeout> | null = null;

// Lists are refetched after my own changes and (debounced) after realtime events.
export const useConversations = create<ConversationsState>()((set, get) => ({
  chats: null,
  archived: null,

  loadChats: async () => {
    const requestedAt = Date.now();
    const chats = await apiRequest<ConversationSummary[]>("/conversations");
    set({ chats });
    // The list carries the server's presence for DM partners. It corrects stale live state
    // (e.g. after a reconnect missed offline events) but never overrides a newer live event.
    usePresenceStore.getState().mergeSnapshot(
      chats
        .filter((chat) => chat.other_user_id !== null)
        .map((chat) => [
          chat.other_user_id as number,
          { online: chat.other_user_online ?? false, lastSeenAt: chat.other_user_last_seen_at },
        ]),
      requestedAt,
    );
  },

  loadArchived: async () => {
    set({ archived: await apiRequest<ConversationSummary[]>("/conversations?archived=true") });
  },

  setPreferences: async (conversationId, changes) => {
    const detail = await apiRequest<ConversationDetail>(`/conversations/${conversationId}/preferences`, {
      method: "PATCH",
      body: changes,
    });
    await Promise.all([get().loadChats(), get().archived ? get().loadArchived() : Promise.resolve()]);
    return detail;
  },

  openDirect: async (userId) => {
    const detail = await apiRequest<ConversationDetail>("/conversations/direct", {
      method: "POST",
      body: { user_id: userId },
    });
    await get().loadChats();
    return detail;
  },

  refreshSoon: () => {
    if (refreshTimer) clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => {
      refreshTimer = null;
      get().loadChats().catch(() => undefined);
    }, REFRESH_DEBOUNCE_MS);
  },
}));
