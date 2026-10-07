"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";

import { type AuthStatus, useAuthStore } from "@/store/auth";

import { AuthSplash } from "./AuthSplash";

// Client-side guards: the token lives in localStorage, which server code (proxy.ts) can't read.

const HOME_FOR: Record<Exclude<AuthStatus, "checking">, string> = {
  signedOut: "/register",
  needsProfile: "/onboarding",
  ready: "/chats",
};

function useGuard(allowed: readonly AuthStatus[]): boolean {
  const status = useAuthStore((state) => state.status);
  const router = useRouter();
  const isAllowed = allowed.includes(status);

  useEffect(() => {
    if (status !== "checking" && !isAllowed) {
      router.replace(HOME_FOR[status]);
    }
  }, [status, isAllowed, router]);

  return isAllowed;
}

/** /register, /verify: only for signed-out visitors. */
export function GuestOnly({ children }: { children: ReactNode }) {
  return useGuard(["signedOut"]) ? children : <AuthSplash />;
}

/** /onboarding: signed in, profile not finished yet. */
export function RequireSignedInWithoutProfile({ children }: { children: ReactNode }) {
  return useGuard(["needsProfile"]) ? children : <AuthSplash />;
}

/** The app: signed in with a finished profile. */
export function RequireAuth({ children }: { children: ReactNode }) {
  return useGuard(["ready"]) ? children : <AuthSplash />;
}

/** "/": just sends everyone to the right place. */
export function RootRedirect() {
  useGuard([]);
  return <AuthSplash />;
}
