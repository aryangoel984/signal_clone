"use client";

import { type LucideIcon, Menu, MessageCircle, Phone, Settings, SquareStack } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { COMING_SOON, showToast } from "@/store/toasts";

type NavItem = { href: string; label: string; icon: LucideIcon };

const ITEMS: NavItem[] = [
  { href: "/chats", label: "Chats", icon: MessageCircle },
  { href: "/calls", label: "Calls", icon: Phone },
  { href: "/stories", label: "Stories", icon: SquareStack },
];

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      aria-label={item.label}
      title={item.label}
      aria-current={active ? "page" : undefined}
      className={`flex h-10 w-[58px] items-center justify-center rounded-lg text-text-primary transition-colors hover:bg-selected ${active ? "bg-selected" : ""}`}
    >
      <Icon size={20} strokeWidth={1.75} fill={active && item.href === "/chats" ? "currentColor" : "none"} aria-hidden />
    </Link>
  );
}

/** The narrow column on the far left: navigation between Chats, Calls, Stories and Settings. */
export function NavRail() {
  const pathname = usePathname();
  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <nav aria-label="Main" className="flex w-[var(--nav-rail-width)] shrink-0 flex-col items-center border-r border-border bg-sidebar py-2">
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
        {ITEMS.map((item) => (
          <NavLink key={item.href} item={item} active={isActive(item.href)} />
        ))}
      </div>
      <div className="mt-auto">
        <NavLink item={{ href: "/settings", label: "Settings", icon: Settings }} active={isActive("/settings")} />
      </div>
    </nav>
  );
}
