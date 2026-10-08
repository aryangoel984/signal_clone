"use client";

import { type ReactNode, useEffect } from "react";

import { Toaster } from "@/components/Toaster";
import { useRealtime } from "@/hooks/useRealtime";
import { useSettings } from "@/store/settings";

import { NavRail } from "./NavRail";

/** Full-height app frame: nav rail on the left, the current section beside it. */
export function AppShell({ children }: { children: ReactNode }) {
  useRealtime();
  const loadSettings = useSettings((state) => state.load);
  useEffect(() => {
    loadSettings().catch(() => undefined); // also syncs the cached theme with the account
  }, [loadSettings]);
  return (
    <div className="flex h-dvh overflow-hidden bg-chat">
      <NavRail />
      <div className="flex min-w-0 flex-1">{children}</div>
      <Toaster />
    </div>
  );
}
