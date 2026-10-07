import type { ReactNode } from "react";

import { Toaster } from "@/components/Toaster";

import { NavRail } from "./NavRail";

/** Full-height app frame: nav rail on the left, the current section beside it. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-dvh overflow-hidden bg-chat">
      <NavRail />
      <div className="flex min-w-0 flex-1">{children}</div>
      <Toaster />
    </div>
  );
}
