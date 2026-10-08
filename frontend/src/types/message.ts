import type { MessageKind, MessageStatus } from "@/types/conversation";

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
