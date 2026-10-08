import { create } from "zustand";

/** Bumped by group.updated so an open chat refetches its details (names, members, roles). */
export const useRevisions = create<{ byConversation: Record<number, number>; bump: (conversationId: number) => void }>()(
  (set, get) => ({
    byConversation: {},
    bump: (conversationId) =>
      set({ byConversation: { ...get().byConversation, [conversationId]: (get().byConversation[conversationId] ?? 0) + 1 } }),
  }),
);
