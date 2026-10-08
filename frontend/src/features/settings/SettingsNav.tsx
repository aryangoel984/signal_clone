"use client";

import { Bell, ChartPie, CircleUserRound, History, Lock, type LucideIcon, MessageCircle, Phone, Settings, SunMoon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Avatar } from "@/components/Avatar";
import { useAuthStore } from "@/store/auth";

type Item = { slug: string; label: string; icon: LucideIcon };

const TOP: Item[] = [{ slug: "account", label: "Account", icon: CircleUserRound }];
const SECTIONS: Item[] = [
  { slug: "general", label: "General", icon: Settings },
  { slug: "appearance", label: "Appearance", icon: SunMoon },
  { slug: "chats", label: "Chats", icon: MessageCircle },
  { slug: "calls", label: "Calls", icon: Phone },
  { slug: "notifications", label: "Notifications", icon: Bell },
  { slug: "privacy", label: "Privacy", icon: Lock },
  { slug: "data-usage", label: "Data usage", icon: ChartPie },
  { slug: "backups", label: "Backups", icon: History },
];

function NavItem({ item, active }: { item: Item; active: boolean }) {
  const Icon = item.icon;
  return (
    <li>
      <Link
        href={`/settings/${item.slug}`}
        aria-current={active ? "page" : undefined}
        className={`flex items-center gap-3 rounded-lg px-4 py-2.5 text-sm text-text-primary hover:bg-selected ${active ? "bg-selected" : ""}`}
      >
        <Icon size={18} strokeWidth={1.75} aria-hidden />
        {item.label}
      </Link>
    </li>
  );
}

/** Left column of Settings (references 8.52.06 / 8.52.17): title, profile row, sections. */
export function SettingsNav() {
  const pathname = usePathname();
  const user = useAuthStore((state) => state.user);
  const active = pathname.split("/")[2] ?? "general";

  return (
    <aside className="settings-nav flex w-[var(--sidebar-width)] shrink-0 flex-col border-r border-border bg-sidebar">
      <h1 className="px-6 pt-3.5 pb-4 text-xl font-semibold text-text-primary">Settings</h1>
      <nav aria-label="Settings" className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        {user && (
          <Link
            href="/settings/profile"
            className={`mb-2 flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-selected ${active === "profile" ? "bg-selected" : ""}`}
          >
            <Avatar name={user.display_name} color={user.avatar_color} imageUrl={user.avatar_url} size={48} />
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold text-text-primary">{user.display_name}</span>
              <span className="block truncate text-sm text-text-primary">{user.phone_number}</span>
            </span>
          </Link>
        )}
        <ul>{TOP.map((item) => <NavItem key={item.slug} item={item} active={active === item.slug} />)}</ul>
        <hr className="mx-4 my-2 border-border" />
        <ul>{SECTIONS.map((item) => <NavItem key={item.slug} item={item} active={active === item.slug} />)}</ul>
      </nav>
    </aside>
  );
}
