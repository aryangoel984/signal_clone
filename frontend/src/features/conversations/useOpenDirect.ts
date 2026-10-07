"use client";

import { useRouter } from "next/navigation";

import { ApiError } from "@/lib/api";
import { useConversations } from "@/store/conversations";
import { useLeftPane } from "@/store/left-pane";
import { showToast } from "@/store/toasts";

/** Get-or-create the DM with a user, go back to the chat list, and open it. */
export function useOpenDirect(): (userId: number) => Promise<void> {
  const router = useRouter();
  const openDirect = useConversations((state) => state.openDirect);
  const setMode = useLeftPane((state) => state.setMode);

  return async (userId) => {
    try {
      const conversation = await openDirect(userId);
      setMode("chats");
      router.push(`/chats/${conversation.id}`);
    } catch (error) {
      showToast(error instanceof ApiError ? error.detail : "Something went wrong");
    }
  };
}
