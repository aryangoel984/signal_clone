"use client";

import { useEffect, useState } from "react";

import { ApiError, apiRequest } from "@/lib/api";
import type { ConversationDetail } from "@/types/conversation";

import { ChatHeader } from "./ChatHeader";
import { ConversationHero } from "./ConversationHero";

type LoadState =
  | { conversationId: number; kind: "ready"; conversation: ConversationDetail }
  | { conversationId: number; kind: "error"; message: string };

/** One open conversation. Phase 3: header + intro card; the timeline and composer come in phase 4. */
export function ChatView({ conversationId }: { conversationId: number }) {
  const [state, setState] = useState<LoadState | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiRequest<ConversationDetail>(`/conversations/${conversationId}`)
      .then((conversation) => !cancelled && setState({ conversationId, kind: "ready", conversation }))
      .catch(
        (error: unknown) =>
          !cancelled &&
          setState({
            conversationId,
            kind: "error",
            message: error instanceof ApiError && error.status === 404 ? "This conversation doesn't exist." : "Couldn't load this conversation.",
          }),
      );
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  const current = state?.conversationId === conversationId ? state : null; // ignore a previous chat's result
  if (current === null) return <div className="flex-1 bg-chat" aria-busy="true" />;
  if (current.kind === "error") {
    return <div className="flex flex-1 items-center justify-center bg-chat text-sm text-text-secondary">{current.message}</div>;
  }

  return (
    <div className="flex min-w-0 flex-1 flex-col bg-chat">
      <ChatHeader
        conversation={current.conversation}
        onChanged={(conversation) => setState({ conversationId, kind: "ready", conversation })}
      />
      <div className="min-h-0 flex-1 overflow-y-auto px-4">
        <ConversationHero conversation={current.conversation} />
      </div>
    </div>
  );
}
