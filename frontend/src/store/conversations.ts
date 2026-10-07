import { create } from "zustand";

import { apiRequest } from "@/lib/api";
import type { ConversationDetail, ConversationSummary, PreferenceChanges } from "@/types/conversation";

type ConversationsState = {
  chats: ConversationSummary[] | null; // null until first load
  archived: ConversationSummary[] | null;
  loadChats: () => Promise<void>;
  loadArchived: () => Promise<void>;
  setPreferences: (conversationId: number, changes: PreferenceChanges) => Promise<ConversationDetail>;
  openDirect: (userId: number) => Promise<ConversationDetail>;
};

// Lists are refetched after every change. Live updates arrive with WebSockets in phase 5.
export const useConversations = create<ConversationsState>()((set, get) => ({
  chats: null,
  archived: null,

  loadChats: async () => {
    set({ chats: await apiRequest<ConversationSummary[]>("/conversations") });
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
}));
