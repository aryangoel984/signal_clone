"use client";

import { useEffect, useState } from "react";

import { ApiError, apiRequest } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { useMessages } from "@/store/messages";
import type { ConversationDetail } from "@/types/conversation";

import { ChatHeader } from "./ChatHeader";
import { Composer } from "./Composer";
import { Timeline } from "./Timeline";

type LoadState =
  | { kind: "ready"; conversation: ConversationDetail; lastReadAtOpen: number }
  | { kind: "error"; message: string };

/** One open conversation: header, timeline and composer. Remounted per conversation (keyed by id). */
export function ChatView({ conversationId }: { conversationId: number }) {
  const me = useAuthStore((state) => state.user);
  const loadLatest = useMessages((state) => state.loadLatest);
  const send = useMessages((state) => state.send);
  const [state, setState] = useState<LoadState | null>(null);

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

  if (state === null || !me) return <div className="flex-1 bg-chat" aria-busy="true" />;
  if (state.kind === "error") {
    return <div className="flex flex-1 items-center justify-center bg-chat text-sm text-text-secondary">{state.message}</div>;
  }

  const { conversation } = state;
  return (
    <div className="flex min-w-0 flex-1 flex-col bg-chat">
      <ChatHeader
        conversation={conversation}
        onChanged={(updated) => setState({ ...state, conversation: updated })}
      />
      <Timeline conversation={conversation} myId={me.id} lastReadAtOpen={state.lastReadAtOpen} />
      <Composer
        onSend={(text) => void send(conversationId, text, me)}
        disabledReason={
          conversation.is_active ? undefined : "You can't send messages to this group because you're no longer a member."
        }
      />
    </div>
  );
}
