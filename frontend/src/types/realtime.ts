import type { MessageStatus } from "@/types/conversation";
import type { Message } from "@/types/message";

/** Server -> client events (mirrors backend app/ws/events.py and PLAN section 3). */
export type ServerEvent =
  | { type: "message.new"; payload: { conversation_id: number; message: Message } }
  | {
      type: "message.status";
      payload: { conversation_id: number; updates: { message_id: number; status: MessageStatus }[] };
    }
  | { type: "typing.start" | "typing.stop"; payload: { conversation_id: number; user_id: number } }
  | { type: "presence.update"; payload: { user_id: number; online: boolean; last_seen_at: string | null } }
  | {
      type: "group.updated";
      payload: { conversation_id: number; change: string; actor_id: number; target_ids: number[] };
    }
  | { type: "message.deleted"; payload: { conversation_id: number; message_id: number } }
  | {
      type: "reaction.updated";
      payload: { conversation_id: number; message_id: number; user_id: number; emoji: string | null };
    }
  | { type: "error"; payload: { detail: string } }
  | { type: "pong"; payload: Record<string, never> };

/** Client -> server frames. */
export type ClientFrame =
  | { type: "typing.start" | "typing.stop"; payload: { conversation_id: number } }
  | { type: "ping"; payload: Record<string, never> };
