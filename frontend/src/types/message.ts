import type { MessageKind, MessageStatus } from "@/types/conversation";

/** Signal's tombstone text (same as the backend's DELETED_TEXT). */
export const DELETED_TEXT = "This message was deleted";

/** Signal allows "Delete for everyone" within 24 hours of sending (the backend enforces it too). */
export const DELETE_FOR_EVERYONE_WINDOW_MS = 24 * 60 * 60 * 1000;

/** Signal's default reaction set; the backend accepts only these (`ReactionEmoji`). */
export const REACTION_EMOJI = ["❤️", "👍", "👎", "😂", "😮", "😢"] as const;
export type ReactionEmoji = (typeof REACTION_EMOJI)[number];

/** The message a reply quotes, as I see it. Mirrors backend `Quote`. */
export type Quote = {
  id: number;
  sender_id: number | null;
  author_name: string; // "You" for my own messages
  text: string;
};

export type Reaction = { user_id: number; emoji: string };

/** Mirrors backend `MessageOut`. */
export type Message = {
  id: number;
  conversation_id: number;
  client_id: string | null;
  kind: MessageKind;
  text: string;
  sender_id: number | null;
  sender_name: string | null; // null for my own and system messages
  sender_avatar_color: string | null;
  sender_avatar_url: string | null;
  created_at: string;
  status: MessageStatus | null;
  deleted: boolean; // deleted for everyone: text is the tombstone, no quote or reactions
  reply_to_id: number | null;
  quote: Quote | null; // null on a reply whose original I can't see: "Original message not found"
  reactions: Reaction[]; // oldest first, one per user
};

export type MessagePage = { items: Message[]; next_cursor: number | null };

/** A message in the UI: server messages plus my optimistic ones that aren't confirmed yet. */
export type ChatMessage = Message & { localStatus?: "sending" | "failed" };

/** Mirrors backend `MessageDetails` (GET /messages/{id}/receipts, sender only). */
export type MessageDetails = {
  message_id: number;
  sent_at: string;
  recipients: {
    user_id: number;
    name: string;
    avatar_color: string;
    avatar_url: string | null;
    delivered_at: string | null;
    read_at: string | null;
  }[];
};
