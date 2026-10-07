"use client";

import type { LucideIcon } from "lucide-react";
import { useEffect, useRef } from "react";

export type MenuItem = {
  label: string;
  icon?: LucideIcon;
  onSelect: () => void;
  danger?: boolean;
};

export type MenuPosition = { top: number; left: number };

type MenuProps = {
  items: MenuItem[];
  position: MenuPosition;
  onClose: () => void;
};

const MENU_WIDTH = 240;

/** Dropdown / context menu at a fixed screen position. Closes on outside click, Escape, scroll or resize. */
export function Menu({ items, position, onClose }: MenuProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ref.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const onPointerDown = (event: PointerEvent) => {
      if (!ref.current?.contains(event.target as Node)) onClose();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", onClose);
    window.addEventListener("scroll", onClose, true);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("resize", onClose);
      window.removeEventListener("scroll", onClose, true);
    };
  }, [onClose]);

  const left = Math.max(8, Math.min(position.left, window.innerWidth - MENU_WIDTH - 8));
  return (
    <div
      ref={ref}
      role="menu"
      className="fixed z-50 rounded-card border border-border-card bg-card py-1.5 shadow-lg"
      style={{ top: position.top, left, width: MENU_WIDTH }}
    >
      {items.map(({ label, icon: Icon, onSelect, danger }) => (
        <button
          key={label}
          type="button"
          role="menuitem"
          onClick={() => {
            onClose();
            onSelect();
          }}
          className={`flex w-full items-center gap-3 px-3 py-1.5 text-left text-sm outline-none hover:bg-selected focus-visible:bg-selected ${danger ? "text-danger" : "text-text-primary"}`}
        >
          {Icon && <Icon size={16} strokeWidth={1.75} aria-hidden />}
          {label}
        </button>
      ))}
    </div>
  );
}

/** Position for a dropdown under the element that opened it. */
export function belowElement(element: HTMLElement): MenuPosition {
  const rect = element.getBoundingClientRect();
  return { top: rect.bottom + 4, left: rect.left };
}
