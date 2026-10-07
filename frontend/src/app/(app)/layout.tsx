"use client";

import { RequireAuth } from "@/features/auth/guards";

export default function AppLayout({ children }: LayoutProps<"/">) {
  return <RequireAuth>{children}</RequireAuth>;
}
