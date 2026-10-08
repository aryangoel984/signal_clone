"use client";

import { useEffect, useRef } from "react";

import type { MenuPosition } from "@/components/Menu";
import { useDismiss } from "@/hooks/useDismiss";
import { REACTION_EMOJI, type ReactionEmoji } from "@/types/message";

type ReactionPickerProps = {
  position: MenuPosition;
  current: string | null; // my reaction on this message, if any
  onPick: (emoji: ReactionEmoji) => void;
  onClose: () => void;
};

const PICKER_WIDTH = 6 * 40 + 12;
const PICKER_HEIGHT = 48;

/** Row of Signal's default reactions; mine is highlighted (picking it again removes it). */
export function ReactionPicker({ position, current, onPick, onClose }: ReactionPickerProps) {
  const ref = useRef<HTMLDivElement>(null);
  useDismiss(ref, onClose);
  useEffect(() => ref.current?.querySelector<HTMLButtonElement>("button")?.focus(), []);

  const left = Math.max(8, Math.min(position.left, window.innerWidth - PICKER_WIDTH - 8));
  const top = Math.max(8, Math.min(position.top, window.innerHeight - PICKER_HEIGHT - 8));
  return (
    <div
      ref={ref}
      role="menu"
      aria-label="React"
      className="fixed z-50 flex gap-1 rounded-full border border-border-card bg-card p-1.5 shadow-lg"
      style={{ top, left }}
    >
      {REACTION_EMOJI.map((emoji) => (
        <button
          key={emoji}
          type="button"
          role="menuitemradio"
          aria-checked={emoji === current}
          aria-label={emoji}
          onClick={() => {
            onClose();
            onPick(emoji);
          }}
          className={`flex h-9 w-9 items-center justify-center rounded-full text-[22px] leading-none outline-none transition-transform hover:scale-110 focus-visible:bg-selected ${
            emoji === current ? "bg-selected" : ""
          }`}
        >
          {emoji}
        </button>
      ))}
    </div>
  );
}

/** Where to open the picker for a bubble: just above it, or below if there's no room. */
export function pickerPositionFor(element: HTMLElement, alignRight: boolean): MenuPosition {
  const rect = element.getBoundingClientRect();
  const top = rect.top - PICKER_HEIGHT - 6 >= 8 ? rect.top - PICKER_HEIGHT - 6 : rect.bottom + 6;
  return { top, left: alignRight ? rect.right - PICKER_WIDTH : rect.left };
}
