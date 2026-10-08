import { type LucideIcon, MessageCircle, Phone, Settings, SquareStack } from "lucide-react";

export type NavItem = { href: string; label: string; icon: LucideIcon };

export const NAV_ITEMS: NavItem[] = [
  { href: "/chats", label: "Chats", icon: MessageCircle },
  { href: "/calls", label: "Calls", icon: Phone },
  { href: "/stories", label: "Stories", icon: SquareStack },
];

export const SETTINGS_ITEM: NavItem = { href: "/settings", label: "Settings", icon: Settings };

export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** Below 900px a single pane is shown; the bottom bar only appears on top-level screens,
 *  not inside a chat or a settings page (those have a back button instead). */
export function showsBottomBar(pathname: string): boolean {
  return !/^\/chats\/[^/]+/.test(pathname) && !/^\/settings\/[^/]+/.test(pathname);
}
