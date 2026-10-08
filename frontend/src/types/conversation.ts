/** Mirrors backend schemas/conversation.py. */

export type ConversationType = "direct" | "group";
export type MessageKind = "text" | "system";
export type MessageStatus = "sent" | "delivered" | "read";
export type MemberRole = "admin" | "member";

export type LastMessage = {
  id: number;
  kind: MessageKind;
  text: string;
  sender_id: number | null;
  sender_name: string | null; // null for my own and system messages
  created_at: string;
  status: MessageStatus | null; // only for my own text messages
};

export type ConversationSummary = {
  id: number;
  type: ConversationType;
  title: string;
  avatar_url: string | null;
  avatar_color: string;
  other_user_id: number | null;
  other_user_online: boolean | null;
  other_user_last_seen_at: string | null;
  is_contact: boolean | null;
  member_count: number;
  is_pinned: boolean;
  is_archived: boolean;
  muted_until: string | null;
  can_send: boolean; // false once I was removed from / left a group (history stays readable)
  unread_count: number;
  last_message: LastMessage | null;
  sort_at: string;
};

export type Member = {
  user_id: number;
  name: string;
  avatar_url: string | null;
  avatar_color: string;
  role: MemberRole;
};

export type ConversationDetail = ConversationSummary & {
  members: Member[];
  my_role: MemberRole;
  groups_in_common: string[];
  last_read_message_id: number;
};

export type PreferenceChanges = Partial<Pick<ConversationSummary, "is_pinned" | "is_archived" | "muted_until">>;
