"use client";

import { useEffect, useState } from "react";

import { GroupSettings } from "@/features/groups/GroupSettings";
import { ApiError, apiRequest } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { useMessages } from "@/store/messages";
import { useRevisions } from "@/store/revisions";
import type { ConversationDetail } from "@/types/conversation";
import type { ChatMessage } from "@/types/message";

import { BlockedBanner } from "./BlockedBanner";
import { ChatHeader } from "./ChatHeader";
import { Composer } from "./Composer";
import { Timeline } from "./Timeline";

type LoadState =
  | { kind: "ready"; conversation: ConversationDetail; lastReadAtOpen: number }
  | { kind: "error"; message: string };

/** One open conversation: header, timeline and composer, or the group settings view.
 *  Remounted per conversation (keyed by id). */
export function ChatView({ conversationId }: { conversationId: number }) {
  const me = useAuthStore((state) => state.user);
  const loadLatest = useMessages((state) => state.loadLatest);
  const send = useMessages((state) => state.send);
  const revision = useRevisions((state) => state.byConversation[conversationId] ?? 0);
  const [state, setState] = useState<LoadState | null>(null);
  const [view, setView] = useState<"chat" | "settings">("chat");
  const [replyTo, setReplyTo] = useState<ChatMessage | null>(null);
  // If the message I'm replying to gets deleted for everyone, the reply is dropped (Signal does the same).
  const replyTargetDeleted = useMessages(
    (state) => replyTo !== null && state.threads[conversationId]?.items.some((m) => m.id === replyTo.id && m.deleted) === true,
  );
  const activeReply = replyTargetDeleted ? null : replyTo;

  useEffect(() => {
    let cancelled = false;
    Promise.all([apiRequest<ConversationDetail>(`/conversations/${conversationId}`), loadLatest(conversationId)])
      .then(([conversation]) => {
        if (!cancelled) setState({ kind: "ready", conversation, lastReadAtOpen: conversation.last_read_message_id });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const notFound = error instanceof ApiError && error.status === 404;
        setState({ kind: "error", message: notFound ? "This conversation doesn't exist." : "Couldn't load this conversation." });
      });
    return () => {
      cancelled = true;
    };
  }, [conversationId, loadLatest]);

  // group.updated (rename, members, roles, my removal): refetch the details in place.
  useEffect(() => {
    if (revision === 0) return;
    let cancelled = false;
    apiRequest<ConversationDetail>(`/conversations/${conversationId}`)
      .then((conversation) => {
        if (!cancelled) setState((current) => (current?.kind === "ready" ? { ...current, conversation } : current));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [conversationId, revision]);

  if (state === null || !me) return <div className="flex-1 bg-chat" aria-busy="true" />;
  if (state.kind === "error") {
    return <div className="flex flex-1 items-center justify-center bg-chat text-sm text-text-secondary">{state.message}</div>;
  }

  const { conversation } = state;
  const update = (updated: ConversationDetail) => setState({ ...state, conversation: updated });

  if (view === "settings" && conversation.type === "group") {
    return <GroupSettings conversation={conversation} myId={me.id} onBack={() => setView("chat")} onChanged={update} />;
  }
  return (
    <div className="flex min-w-0 flex-1 flex-col bg-chat">
      <ChatHeader conversation={conversation} onChanged={update} onOpenSettings={() => setView("settings")} />
      <Timeline conversation={conversation} myId={me.id} lastReadAtOpen={state.lastReadAtOpen} onReply={setReplyTo} />
      {conversation.blocked_by_me ? (
        <BlockedBanner name={conversation.title} userId={conversation.other_user_id} onChanged={update} conversationId={conversationId} />
      ) : (
        <Composer
          conversationId={conversationId}
          myId={me.id}
          onSend={(text) => {
            void send(conversationId, text, me, activeReply);
            setReplyTo(null);
          }}
          replyTo={activeReply}
          onCancelReply={() => setReplyTo(null)}
          disabledReason={
            conversation.can_send ? undefined : "You can't send messages to this group because you're no longer a member."
          }
        />
      )}
    </div>
  );
}
