"use client";

import { useParams } from "next/navigation";

import { ChatView } from "@/features/chat/ChatView";

export default function ConversationPage() {
  const { conversationId } = useParams<{ conversationId: string }>();
  const id = Number(conversationId);
  if (!Number.isInteger(id) || id <= 0) {
    return <div className="flex flex-1 items-center justify-center bg-chat text-sm text-text-secondary">This conversation doesn&apos;t exist.</div>;
  }
  return <ChatView key={id} conversationId={id} />;
}
