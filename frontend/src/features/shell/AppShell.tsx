"use client";

import { type ReactNode, useEffect } from "react";

import { Toaster } from "@/components/Toaster";
import { useRealtime } from "@/hooks/useRealtime";
import { useSettings } from "@/store/settings";

import { BottomNav, NavRail } from "./NavRail";

/** Full-height app frame: nav rail on the left, the current section beside it. */
export function AppShell({ children }: { children: ReactNode }) {
  useRealtime();
  const loadSettings = useSettings((state) => state.load);
  useEffect(() => {
    loadSettings().catch(() => undefined); // also syncs the cached theme with the account
  }, [loadSettings]);
  return (
    // 100dvh: the dynamic viewport height, which excludes mobile browser chrome and the keyboard.
    <div className="flex h-dvh flex-col overflow-hidden bg-chat pt-[env(safe-area-inset-top)] pane:flex-row">
      <NavRail />
      <div className="flex min-h-0 min-w-0 flex-1">{children}</div>
      <BottomNav />
      <Toaster />
    </div>
  );
}
