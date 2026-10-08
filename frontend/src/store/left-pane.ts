import { create } from "zustand";

/** Which panel the left column shows (Signal swaps it in place rather than using modals). */
export type LeftPaneMode = "chats" | "archive" | "compose" | "findUsername" | "findPhone" | "newGroup";

type LeftPaneState = {
  mode: LeftPaneMode;
  query: string;
  unreadOnly: boolean;
  setMode: (mode: LeftPaneMode) => void;
  setQuery: (query: string) => void;
  toggleUnreadOnly: () => void;
};

export const useLeftPane = create<LeftPaneState>()((set) => ({
  mode: "chats",
  query: "",
  unreadOnly: false,
  setMode: (mode) => set({ mode, query: "" }),
  setQuery: (query) => set({ query }),
  toggleUnreadOnly: () => set((state) => ({ unreadOnly: !state.unreadOnly })),
}));
