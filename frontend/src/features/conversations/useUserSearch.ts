"use client";

import { useEffect, useState } from "react";

import { apiRequest } from "@/lib/api";
import type { UserPublic } from "@/types/contact";

const DEBOUNCE_MS = 200;

/** Debounced `/users/search`. Returns null while a search for the current query is pending. */
export function useUserSearch(query: string): UserPublic[] | null {
  const [result, setResult] = useState<{ query: string; users: UserPublic[] } | null>(null);
  const trimmed = query.trim();

  useEffect(() => {
    if (!trimmed) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      apiRequest<UserPublic[]>(`/users/search?q=${encodeURIComponent(trimmed)}`)
        .then((users) => !cancelled && setResult({ query: trimmed, users }))
        .catch(() => !cancelled && setResult({ query: trimmed, users: [] }));
    }, DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [trimmed]);

  if (!trimmed) return [];
  return result?.query === trimmed ? result.users : null;
}
