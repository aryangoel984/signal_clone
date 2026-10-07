"use client";

import { GuestOnly } from "@/features/auth/guards";

export default function GuestLayout({ children }: LayoutProps<"/">) {
  return <GuestOnly>{children}</GuestOnly>;
}
