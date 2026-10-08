import { create } from "zustand";

/** Who is typing where. Each entry clears itself after 5 s if no typing.stop arrives. */
const SAFETY_TIMEOUT_MS = 5_000;
const timers = new Map<string, ReturnType<typeof setTimeout>>();

type TypingState = {
  byConversation: Record<number, number[]>; // conversation id -> user ids typing
  start: (conversationId: number, userId: number) => void;
  stop: (conversationId: number, userId: number) => void;
};

export const useTyping = create<TypingState>()((set, get) => ({
  byConversation: {},

  start: (conversationId, userId) => {
    const key = `${conversationId}:${userId}`;
    const existing = timers.get(key);
    if (existing) clearTimeout(existing);
    timers.set(key, setTimeout(() => get().stop(conversationId, userId), SAFETY_TIMEOUT_MS));
    const current = get().byConversation[conversationId] ?? [];
    if (!current.includes(userId)) {
      set({ byConversation: { ...get().byConversation, [conversationId]: [...current, userId] } });
    }
  },

  stop: (conversationId, userId) => {
    const key = `${conversationId}:${userId}`;
    const existing = timers.get(key);
    if (existing) clearTimeout(existing);
    timers.delete(key);
    const current = get().byConversation[conversationId] ?? [];
    if (current.includes(userId)) {
      set({ byConversation: { ...get().byConversation, [conversationId]: current.filter((id) => id !== userId) } });
    }
  },
}));

const NO_ONE: number[] = [];
export function useTypingIn(conversationId: number): number[] {
  return useTyping((state) => state.byConversation[conversationId] ?? NO_ONE);
}
