import { Copy, Ellipsis, Info, Reply, SmilePlus } from "lucide-react";
import { useRef, useState } from "react";

import { Avatar } from "@/components/Avatar";
import { IconButton } from "@/components/IconButton";
import { belowElement, Menu, type MenuPosition } from "@/components/Menu";
import { StatusTicks } from "@/components/StatusTicks";
import { formatBubbleTime } from "@/lib/format-time";
import { nameColor } from "@/lib/name-color";
import { showToast } from "@/store/toasts";
import type { ChatMessage, ReactionEmoji } from "@/types/message";

import { QuoteBlock } from "./QuoteBlock";
import { pickerPositionFor, ReactionPicker } from "./ReactionPicker";
import { ReactionPills } from "./ReactionPills";

type MessageBubbleProps = {
  message: ChatMessage;
  myId: number;
  mine: boolean;
  /** Position inside a run of consecutive messages from the same sender. */
  first: boolean;
  last: boolean;
  isGroup: boolean;
  highlighted: boolean; // briefly, after jumping here from a quote
  onRetry: (clientId: string) => void;
  onShowDetails: (messageId: number) => void;
  onReply: (message: ChatMessage) => void;
  onReact: (messageId: number, emoji: ReactionEmoji | null) => void;
  onJumpTo: (messageId: number) => void;
};

const AVATAR_SIZE = 28;

export function MessageBubble(props: MessageBubbleProps) {
  const { message, myId, mine, first, last, isGroup, highlighted } = props;
  const [menu, setMenu] = useState<MenuPosition | null>(null);
  const [picker, setPicker] = useState<MenuPosition | null>(null);
  const bubble = useRef<HTMLDivElement>(null);
  const confirmed = message.id > 0 && !message.localStatus;
  const quote = message.quote;
  const myReaction = message.reactions.find((reaction) => reaction.user_id === myId)?.emoji ?? null;

  const openPicker = () => bubble.current && setPicker(pickerPositionFor(bubble.current, mine));
  // Picking my current reaction again removes it (Signal).
  const toggleReaction = (emoji: string) => props.onReact(message.id, emoji === myReaction ? null : (emoji as ReactionEmoji));

  // Signal's hover actions next to the bubble: react, reply, more.
  const actions = (
    <div className={`flex self-center opacity-0 group-hover:opacity-100 focus-within:opacity-100 ${mine ? "flex-row-reverse" : ""}`}>
      <IconButton icon={SmilePlus} size={16} label="React" className="text-text-secondary" onClick={openPicker} />
      <IconButton icon={Reply} size={16} label="Reply" className="text-text-secondary" onClick={() => props.onReply(message)} />
      <IconButton
        icon={Ellipsis}
        size={16}
        label="Message actions"
        className="text-text-secondary"
        onClick={(event) => setMenu(belowElement(event.currentTarget))}
      />
    </div>
  );
  const showGroupDetails = isGroup && !mine;
  const status = message.localStatus === "sending" ? "sending" : message.status;

  // Corners touching a neighbour from the same sender are tighter (Signal's grouped bubbles).
  const corners = mine
    ? `${first ? "" : "rounded-tr-[4px]"} ${last ? "" : "rounded-br-[4px]"}`
    : `${first ? "" : "rounded-tl-[4px]"} ${last ? "" : "rounded-bl-[4px]"}`;

  return (
    <div
      data-bubble-id={message.id > 0 ? message.id : undefined}
      className={`group flex items-end gap-2 rounded-[10px] transition-colors duration-700 ${mine ? "justify-end" : "justify-start"} ${
        first ? "mt-3" : "mt-0.5"
      } ${message.reactions.length > 0 ? "mb-1.5" : ""} ${highlighted ? "bg-primary/15" : ""}`}
    >
      {mine && confirmed && actions}
      {showGroupDetails &&
        (last ? (
          <Avatar name={message.sender_name} color={message.sender_avatar_color ?? "A210"} imageUrl={message.sender_avatar_url} size={AVATAR_SIZE} />
        ) : (
          <span style={{ width: AVATAR_SIZE }} className="shrink-0" />
        ))}
      <div className={`flex max-w-[min(70%,560px)] flex-col ${mine ? "items-end" : "items-start"}`}>
        <div
          ref={bubble}
          onContextMenu={(event) => {
            if (!confirmed) return;
            event.preventDefault();
            setMenu({ top: event.clientY, left: event.clientX });
          }}
          data-message-id={!mine && message.id > 0 ? message.id : undefined}
          className={`rounded-[18px] px-3 py-[7px] text-sm leading-5 ${corners} ${
            mine ? "bg-bubble-outgoing text-on-bubble-outgoing" : "bg-bubble-incoming text-on-bubble-incoming"
          } ${message.localStatus === "failed" ? "opacity-60" : ""} ${message.reply_to_id !== null ? "min-w-[180px]" : ""}`}
        >
          {showGroupDetails && first && message.sender_id !== null && (
            <div className="text-[13px] font-semibold" style={{ color: nameColor(message.sender_id) }}>
              {message.sender_name}
            </div>
          )}
          {message.reply_to_id !== null && (
            <div className="mt-[3px] mb-1.5">
              <QuoteBlock
                quote={quote}
                tone={mine ? "outgoing" : "incoming"}
                onClick={quote ? () => props.onJumpTo(quote.id) : undefined}
              />
            </div>
          )}
          <div className="break-words whitespace-pre-wrap">
            {message.text}
            {last && (
              <span
                className={`float-right mt-[5px] ml-3 inline-flex items-center gap-1 text-[11px] leading-none ${
                  mine ? "text-on-bubble-outgoing/80" : "text-text-secondary"
                }`}
              >
                {formatBubbleTime(message.created_at)}
                {mine && status && <StatusTicks status={status} size={15} checkColor="var(--bubble-outgoing)" />}
              </span>
            )}
          </div>
        </div>
        <ReactionPills reactions={message.reactions} myId={myId} onToggle={toggleReaction} />
        {message.localStatus === "failed" && message.client_id && (
          <button type="button" onClick={() => props.onRetry(message.client_id as string)} className="mt-1 text-xs text-danger hover:underline">
            Not sent. Click to retry.
          </button>
        )}
      </div>
      {!mine && confirmed && actions}
      {menu && (
        <Menu
          position={menu}
          onClose={() => setMenu(null)}
          items={[
            { label: "React", icon: SmilePlus, onSelect: openPicker },
            { label: "Reply", icon: Reply, onSelect: () => props.onReply(message) },
            ...(mine ? [{ label: "Message details", icon: Info, onSelect: () => props.onShowDetails(message.id) }] : []),
            {
              label: "Copy text",
              icon: Copy,
              onSelect: () =>
                void navigator.clipboard
                  .writeText(message.text)
                  .then(() => showToast("Copied"))
                  .catch(() => showToast("Couldn't copy")),
            },
          ]}
        />
      )}
      {picker && <ReactionPicker position={picker} current={myReaction} onPick={toggleReaction} onClose={() => setPicker(null)} />}
    </div>
  );
}
