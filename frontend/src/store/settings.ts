import { create } from "zustand";

import { apiRequest } from "@/lib/api";
import { applyTheme } from "@/lib/theme";
import type { Settings } from "@/types/settings";

type SettingsState = {
  settings: Settings | null;
  load: () => Promise<void>;
  update: (changes: Partial<Settings>) => Promise<void>;
};

// Bumped by every change. A load that started before a change must not overwrite it
// (e.g. the user picks Dark while the initial load is still in flight).
let changeCounter = 0;

/** The signed-in user's settings (user_settings). Loading also syncs the cached theme. */
export const useSettings = create<SettingsState>()((set, get) => ({
  settings: null,

  load: async () => {
    const startedAt = changeCounter;
    const settings = await apiRequest<Settings>("/users/me/settings");
    if (startedAt !== changeCounter) return; // a newer change already set the state
    applyTheme(settings.theme);
    set({ settings });
  },

  update: async (changes) => {
    changeCounter += 1;
    const previous = get().settings;
    if (previous) set({ settings: { ...previous, ...changes } }); // optimistic: toggles feel instant
    if (changes.theme) applyTheme(changes.theme);
    try {
      set({ settings: await apiRequest<Settings>("/users/me/settings", { method: "PATCH", body: changes }) });
    } catch (error) {
      set({ settings: previous });
      if (previous && changes.theme) applyTheme(previous.theme);
      throw error;
    }
  },
}));
