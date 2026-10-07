"use client";

import { useEffect } from "react";

import { useAuthStore } from "@/store/auth";

/** Mounted once in the root layout: restores the session after the first render. */
export function AuthBootstrap() {
  const hydrate = useAuthStore((state) => state.hydrate);
  useEffect(() => hydrate(), [hydrate]);
  return null;
}
