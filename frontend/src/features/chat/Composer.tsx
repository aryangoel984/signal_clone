"use client";

import { ArrowUp, File, Image as ImageIcon, ListChecks, Mic, Plus, Smile, X } from "lucide-react";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";

import { IconButton } from "@/components/IconButton";
import { useTypingSender } from "@/hooks/useTypingSender";
import { useSettings } from "@/store/settings";
import { Menu, type MenuPosition } from "@/components/Menu";
import { quoteOf } from "@/store/messages";
import { COMING_SOON, showToast } from "@/store/toasts";
import type { ChatMessage } from "@/types/message";

import { QuoteBlock } from "./QuoteBlock";

type ComposerProps = {
  conversationId: number;
  myId: number;
  onSend: (text: string) => void;
  replyTo: ChatMessage | null; // shown as a quote above the field until sent or cancelled
  onCancelReply: () => void;
  disabledReason?: string; // e.g. removed from the group: replaces the composer
};

const MAX_LINES = 6;
const LINE_HEIGHT_PX = 20;

/** Signal's composer: emoji, auto-growing "Message" field, mic that becomes send, and +. */
export function Composer({ conversationId, myId, onSend, replyTo, onCancelReply, disabledReason }: ComposerProps) {
  const [text, setText] = useState("");
  const typing = useTypingSender(conversationId);
  const enterSends = useSettings((state) => state.settings?.enter_key_sends ?? true);
  const [attachMenu, setAttachMenu] = useState<MenuPosition | null>(null);
  const field = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (replyTo) field.current?.focus(); // "Reply" puts the cursor in the field, like Signal
  }, [replyTo]);

  if (disabledReason) {
    return <div className="shrink-0 px-6 py-4 text-center text-sm text-text-secondary">{disabledReason}</div>;
  }

  function resize(element: HTMLTextAreaElement) {
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, MAX_LINES * LINE_HEIGHT_PX + 16)}px`;
  }

  function send() {
    const trimmed = text.trim();
    if (!trimmed) return;
    typing.stopped();
    onSend(trimmed);
    setText("");
    if (field.current) {
      field.current.value = "";
      resize(field.current);
      field.current.focus();
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Escape" && replyTo) {
      event.preventDefault();
      onCancelReply();
      return;
    }
    // "Enter key sends" on: Enter sends, Shift+Enter adds a line. Off: Enter adds a line,
    // Ctrl/Cmd+Enter sends. Never send mid-IME-composition.
    if (event.key !== "Enter" || event.nativeEvent.isComposing) return;
    const sendIt = enterSends ? !event.shiftKey : event.ctrlKey || event.metaKey;
    if (sendIt) {
      event.preventDefault();
      send();
    }
  }

  const hasText = text.trim() !== "";
  return (
    <div className="shrink-0">
      {replyTo && (
        <div className="flex items-center gap-2 px-3 pt-2 pane:px-4">
          <div className="min-w-0 flex-1">
            <QuoteBlock quote={quoteOf(replyTo, myId)} tone="composer" />
          </div>
          <IconButton icon={X} label="Cancel reply" size={18} onClick={onCancelReply} />
        </div>
      )}
      <div className="flex items-end gap-2 px-3 pt-1 pb-[max(0.75rem,env(safe-area-inset-bottom))] pane:px-4">
        <IconButton icon={Smile} label="Emoji" size={22} onClick={() => showToast(COMING_SOON)} className="mb-0.5" />
        <textarea
          ref={field}
          rows={1}
          value={text}
          placeholder="Message"
          aria-label="Message"
          onChange={(event) => {
            setText(event.target.value);
            resize(event.target);
            if (event.target.value.trim()) typing.typed();
            else typing.stopped();
          }}
          onBlur={typing.stopped}
          onKeyDown={handleKeyDown}
          className="min-h-[34px] flex-1 resize-none rounded-[18px] bg-composer px-4 py-[7px] text-sm leading-5 text-text-primary outline-none placeholder:text-text-muted focus:ring-1 focus:ring-primary"
        />
        {hasText ? (
          <button
            type="button"
            aria-label="Send"
            onClick={send}
            className="mb-px flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-on-primary hover:brightness-110"
          >
            <ArrowUp size={18} strokeWidth={2.25} aria-hidden />
          </button>
        ) : (
          <IconButton icon={Mic} label="Voice message" size={22} onClick={() => showToast(COMING_SOON)} className="mb-0.5" />
        )}
        <IconButton
          icon={Plus}
          label="Attach"
          size={22}
          className="mb-0.5"
          onClick={(event) => {
            const rect = event.currentTarget.getBoundingClientRect();
            setAttachMenu({ top: rect.top - 128, left: rect.right - 240 });
          }}
        />
        {attachMenu && (
          <Menu
            position={attachMenu}
            onClose={() => setAttachMenu(null)}
            items={[
              { label: "Photos & videos", icon: ImageIcon, onSelect: () => showToast(COMING_SOON) },
              { label: "File", icon: File, onSelect: () => showToast(COMING_SOON) },
              { label: "Poll", icon: ListChecks, onSelect: () => showToast(COMING_SOON) },
            ]}
          />
        )}
      </div>
    </div>
  );
}
