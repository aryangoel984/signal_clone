"use client";

import { Button } from "@/components/Button";
import { apiRequest } from "@/lib/api";
import { useConversations } from "@/store/conversations";
import { showToast } from "@/store/toasts";
import type { ConversationDetail } from "@/types/conversation";

type BlockedBannerProps = {
  conversationId: number;
  name: string;
  userId: number | null;
  onChanged: (conversation: ConversationDetail) => void;
};

/** Replaces the composer in a DM with someone I blocked (sending would be refused). */
export function BlockedBanner({ conversationId, name, userId, onChanged }: BlockedBannerProps) {
  const loadChats = useConversations((state) => state.loadChats);

  async function unblock() {
    try {
      await apiRequest<void>(`/blocks/${userId}`, { method: "DELETE" });
      await loadChats();
      onChanged(await apiRequest<ConversationDetail>(`/conversations/${conversationId}`));
      showToast("Unblocked");
    } catch {
      showToast("Couldn't unblock");
    }
  }

  return (
    <div className="flex shrink-0 flex-col items-center gap-2 px-6 py-4 text-center">
      <p className="text-sm text-text-secondary">You blocked {name}. Unblock to send messages.</p>
      <Button variant="secondary" onClick={() => void unblock()}>
        Unblock
      </Button>
    </div>
  );
}
