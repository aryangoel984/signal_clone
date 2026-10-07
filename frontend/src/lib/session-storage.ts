// Where the session lives in the browser. Token in localStorage (not an httpOnly cookie):
// the API is on a different site than the frontend and WebSockets need the token
// explicitly anyway. See docs/PLAN.md, "Auth token storage".
//
// Every access is wrapped in try/catch: storage can be unavailable (private mode,
// blocked site data), and the app must still render.

import type { Me } from "@/types/user";

const TOKEN_KEY = "signal.token";
const USER_KEY = "signal.user";
const PENDING_PHONE_KEY = "signal.pendingPhone";

function read(storage: () => Storage, key: string): string | null {
  try {
    return storage().getItem(key);
  } catch {
    return null;
  }
}

function write(storage: () => Storage, key: string, value: string | null): void {
  try {
    if (value === null) storage().removeItem(key);
    else storage().setItem(key, value);
  } catch {
    // Storage unavailable: the session just won't survive a reload.
  }
}

const local = () => window.localStorage;
const session = () => window.sessionStorage;

export function loadSession(): { token: string; user: Me | null } | null {
  const token = read(local, TOKEN_KEY);
  if (!token) return null;
  const cached = read(local, USER_KEY);
  try {
    return { token, user: cached ? (JSON.parse(cached) as Me) : null };
  } catch {
    return { token, user: null };
  }
}

export function saveSession(token: string, user: Me): void {
  write(local, TOKEN_KEY, token);
  saveCachedUser(user);
}

export function saveCachedUser(user: Me): void {
  write(local, USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
  write(local, TOKEN_KEY, null);
  write(local, USER_KEY, null);
}

export function getToken(): string | null {
  return read(local, TOKEN_KEY);
}

/** The number being verified, handed from /register to /verify (per tab, not in the URL). */
export function loadPendingPhone(): string | null {
  return read(session, PENDING_PHONE_KEY);
}

export function savePendingPhone(phone: string | null): void {
  write(session, PENDING_PHONE_KEY, phone);
}
