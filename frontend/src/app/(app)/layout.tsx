"use client";

import { RequireAuth } from "@/features/auth/guards";
import { AppShell } from "@/features/shell/AppShell";

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <RequireAuth>
      <AppShell>{children}</AppShell>
    </RequireAuth>
  );
}
