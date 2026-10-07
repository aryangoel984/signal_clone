import { create } from "zustand";

import { apiRequest, setUnauthorizedHandler } from "@/lib/api";
import { clearSession, loadSession, saveCachedUser, saveSession } from "@/lib/session-storage";
import type { Me } from "@/types/user";

/**
 * checking     - not yet read from storage (server render + first client render)
 * signedOut    - no session
 * needsProfile - signed in but onboarding (display name) not finished
 * ready        - signed in with a profile
 */
export type AuthStatus = "checking" | "signedOut" | "needsProfile" | "ready";

type AuthState = {
  status: AuthStatus;
  user: Me | null;
  hydrate: () => void;
  signIn: (token: string, user: Me) => void;
  setUser: (user: Me) => void;
  signOut: () => Promise<void>;
};

function statusFor(user: Me | null): AuthStatus {
  return user?.display_name ? "ready" : "needsProfile";
}

export const useAuthStore = create<AuthState>()((set, get) => ({
  status: "checking",
  user: null,

  /** Runs once after mount: restores the session from storage synchronously (no network
   *  wait, no flash of the wrong screen), then revalidates the profile in the background. */
  hydrate: () => {
    if (get().status !== "checking") return;
    const stored = loadSession();
    if (!stored) {
      set({ status: "signedOut", user: null });
      return;
    }
    set({ status: statusFor(stored.user), user: stored.user });

    apiRequest<Me>("/users/me")
      .then((user) => get().setUser(user))
      .catch(() => {
        // A 401 already signed us out via the unauthorized handler. Network errors keep
        // the cached profile so the app still opens offline.
      });
  },

  signIn: (token, user) => {
    saveSession(token, user);
    set({ status: statusFor(user), user });
  },

  setUser: (user) => {
    saveCachedUser(user);
    set({ status: statusFor(user), user });
  },

  signOut: async () => {
    try {
      await apiRequest<void>("/auth/logout", { method: "POST" });
    } catch {
      // Already invalid or offline: clearing locally is what matters.
    }
    clearSession();
    set({ status: "signedOut", user: null });
  },
}));

setUnauthorizedHandler(() => {
  clearSession();
  useAuthStore.setState({ status: "signedOut", user: null });
});
