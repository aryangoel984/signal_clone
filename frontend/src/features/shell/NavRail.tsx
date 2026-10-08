"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useConversations } from "@/store/conversations";
import { COMING_SOON, showToast } from "@/store/toasts";

import { isActive, NAV_ITEMS, type NavItem, SETTINGS_ITEM, showsBottomBar } from "./navItems";

function Badge({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <span
      aria-label={`${count} unread`}
      className="absolute -top-1.5 -right-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] leading-none font-semibold text-on-primary"
    >
      {count > 99 ? "99+" : count}
    </span>
  );
}

function NavLink({ item, active, badge = 0 }: { item: NavItem; active: boolean; badge?: number }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      aria-label={item.label}
      title={item.label}
      aria-current={active ? "page" : undefined}
      className={`flex h-10 w-[58px] items-center justify-center rounded-lg text-text-primary transition-colors hover:bg-selected ${active ? "bg-selected" : ""}`}
    >
      <span className="relative">
        <Icon size={20} strokeWidth={1.75} fill={active && item.href === "/chats" ? "currentColor" : "none"} aria-hidden />
        <Badge count={badge} />
      </span>
    </Link>
  );
}

function useUnreadTotal(): number {
  return useConversations((state) => (state.chats ?? []).reduce((sum, chat) => sum + chat.unread_count, 0));
}

/** Desktop (900px+): the narrow column on the far left. */
export function NavRail() {
  const pathname = usePathname();
  const unread = useUnreadTotal();
  return (
    <nav aria-label="Main" className="hidden w-[var(--nav-rail-width)] shrink-0 flex-col items-center border-r border-border bg-sidebar py-2 pane:flex">
      <button
        type="button"
        aria-label="Menu"
        title="Menu"
        onClick={() => showToast(COMING_SOON)}
        className="mb-3 flex h-10 w-[58px] items-center justify-center rounded-lg text-text-primary hover:bg-selected"
      >
        <Menu size={20} strokeWidth={1.75} aria-hidden />
      </button>
      <div className="flex flex-col gap-2">
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.href} item={item} active={isActive(pathname, item.href)} badge={item.href === "/chats" ? unread : 0} />
        ))}
      </div>
      <div className="mt-auto">
        <NavLink item={SETTINGS_ITEM} active={isActive(pathname, SETTINGS_ITEM.href)} />
      </div>
    </nav>
  );
}

/** Below 900px: the same destinations as a bottom bar, clear of the home indicator. */
export function BottomNav() {
  const pathname = usePathname();
  const unread = useUnreadTotal();
  if (!showsBottomBar(pathname)) return null;
  return (
    <nav
      aria-label="Main"
      className="flex shrink-0 items-center justify-around border-t border-border bg-sidebar pt-1.5 pb-[max(0.375rem,env(safe-area-inset-bottom))] pane:hidden"
    >
      {[...NAV_ITEMS, SETTINGS_ITEM].map((item) => (
        <NavLink key={item.href} item={item} active={isActive(pathname, item.href)} badge={item.href === "/chats" ? unread : 0} />
      ))}
    </nav>
  );
}
