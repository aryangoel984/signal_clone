import { create } from "zustand";

type Presence = { online: boolean; lastSeenAt: string | null };
type Entry = Presence & { at: number }; // when this client learned it (ms)

/**
 * Live presence. Sources: presence.update events (newest truth) and chat-list loads, which
 * correct stale state after a reconnect. A list snapshot is only applied to users whose last
 * live event is older than the moment that list request *started*; otherwise a slow response
 * could undo a newer event.
 */
export const usePresenceStore = create<{
  byUser: Record<number, Entry>;
  update: (userId: number, presence: Presence) => void;
  mergeSnapshot: (entries: [number, Presence][], requestedAt: number) => void;
}>()((set, get) => ({
  byUser: {},
  update: (userId, presence) => set({ byUser: { ...get().byUser, [userId]: { ...presence, at: Date.now() } } }),
  mergeSnapshot: (entries, requestedAt) => {
    const byUser = { ...get().byUser };
    for (const [userId, presence] of entries) {
      const current = byUser[userId];
      if (!current || current.at <= requestedAt) byUser[userId] = { ...presence, at: requestedAt };
    }
    set({ byUser });
  },
}));

export function usePresence(userId: number | null, fallback: Presence): Presence {
  const live = usePresenceStore((state) => (userId === null ? undefined : state.byUser[userId]));
  return live ?? fallback;
}
