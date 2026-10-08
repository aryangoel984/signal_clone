import { Copy, Ellipsis, Info } from "lucide-react";
import { useState } from "react";

import { Avatar } from "@/components/Avatar";
import { IconButton } from "@/components/IconButton";
import { belowElement, Menu, type MenuPosition } from "@/components/Menu";
import { StatusTicks } from "@/components/StatusTicks";
import { formatBubbleTime } from "@/lib/format-time";
import { nameColor } from "@/lib/name-color";
import { showToast } from "@/store/toasts";
import type { ChatMessage } from "@/types/message";

type MessageBubbleProps = {
  message: ChatMessage;
  mine: boolean;
  /** Position inside a run of consecutive messages from the same sender. */
  first: boolean;
  last: boolean;
  isGroup: boolean;
  onRetry: (clientId: string) => void;
  onShowDetails: (messageId: number) => void;
};

const AVATAR_SIZE = 28;

export function MessageBubble({ message, mine, first, last, isGroup, onRetry, onShowDetails }: MessageBubbleProps) {
  const [menu, setMenu] = useState<MenuPosition | null>(null);
  const confirmed = message.id > 0 && !message.localStatus;
  const showGroupDetails = isGroup && !mine;
  const status = message.localStatus === "sending" ? "sending" : message.status;

  // Corners touching a neighbour from the same sender are tighter (Signal's grouped bubbles).
  const corners = mine
    ? `${first ? "" : "rounded-tr-[4px]"} ${last ? "" : "rounded-br-[4px]"}`
    : `${first ? "" : "rounded-tl-[4px]"} ${last ? "" : "rounded-bl-[4px]"}`;

  return (
    <div className={`group flex items-end gap-2 ${mine ? "justify-end" : "justify-start"} ${first ? "mt-3" : "mt-0.5"}`}>
      {mine && confirmed && (
        <IconButton
          icon={Ellipsis}
          size={16}
          label="Message actions"
          className="self-center text-text-secondary opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
          onClick={(event) => setMenu(belowElement(event.currentTarget))}
        />
      )}
      {showGroupDetails &&
        (last ? (
          <Avatar name={message.sender_name} color={message.sender_avatar_color ?? "A210"} imageUrl={message.sender_avatar_url} size={AVATAR_SIZE} />
        ) : (
          <span style={{ width: AVATAR_SIZE }} className="shrink-0" />
        ))}
      <div className={`flex max-w-[min(70%,560px)] flex-col ${mine ? "items-end" : "items-start"}`}>
        <div
          data-message-id={!mine && message.id > 0 ? message.id : undefined}
          className={`rounded-[18px] px-3 py-[7px] text-sm leading-5 ${corners} ${
            mine ? "bg-bubble-outgoing text-on-bubble-outgoing" : "bg-bubble-incoming text-on-bubble-incoming"
          } ${message.localStatus === "failed" ? "opacity-60" : ""}`}
        >
          {showGroupDetails && first && message.sender_id !== null && (
            <div className="text-[13px] font-semibold" style={{ color: nameColor(message.sender_id) }}>
              {message.sender_name}
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
        {message.localStatus === "failed" && message.client_id && (
          <button type="button" onClick={() => onRetry(message.client_id as string)} className="mt-1 text-xs text-danger hover:underline">
            Not sent. Click to retry.
          </button>
        )}
      </div>
      {menu && (
        <Menu
          position={menu}
          onClose={() => setMenu(null)}
          items={[
            { label: "Message details", icon: Info, onSelect: () => onShowDetails(message.id) },
            {
              label: "Copy text",
              icon: Copy,
              onSelect: () => void navigator.clipboard.writeText(message.text).then(() => showToast("Copied")),
            },
          ]}
        />
      )}
    </div>
  );
}
