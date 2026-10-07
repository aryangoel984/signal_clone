"use client";

import { useRouter } from "next/navigation";

import { ApiError } from "@/lib/api";
import { useConversations } from "@/store/conversations";
import { useLeftPane } from "@/store/left-pane";
import { showToast } from "@/store/toasts";
import type { UserPublic } from "@/types/contact";
import type { ConversationSummary } from "@/types/conversation";

import { ConversationList } from "./ConversationList";
import { SectionHeading, UserRow } from "./UserRow";
import { useUserSearch } from "./useUserSearch";

/** Chat-list search: matching chats by title, then people from /users/search without a chat yet. */
export function SearchResults({ chats, query }: { chats: ConversationSummary[]; query: string }) {
  const router = useRouter();
  const openDirect = useConversations((state) => state.openDirect);
  const setQuery = useLeftPane((state) => state.setQuery);
  const people = useUserSearch(query);

  const needle = query.trim().toLocaleLowerCase();
  const matchingChats = chats.filter((chat) => chat.title.toLocaleLowerCase().includes(needle));
  const chatPartnerIds = new Set(matchingChats.map((chat) => chat.other_user_id));
  const otherPeople = (people ?? []).filter((person) => !chatPartnerIds.has(person.id));

  async function open(person: UserPublic) {
    try {
      const conversation = await openDirect(person.id);
      setQuery("");
      router.push(`/chats/${conversation.id}`);
    } catch (error) {
      showToast(error instanceof ApiError ? error.detail : "Something went wrong");
    }
  }

  if (people !== null && matchingChats.length === 0 && otherPeople.length === 0) {
    return <p className="px-4 pt-8 text-center text-sm text-text-primary">No results for &quot;{query.trim()}&quot;</p>;
  }

  return (
    <div>
      {matchingChats.length > 0 && (
        <>
          <SectionHeading>Chats</SectionHeading>
          <ConversationList chats={matchingChats} />
        </>
      )}
      {otherPeople.length > 0 && (
        <>
          <SectionHeading>Contacts</SectionHeading>
          <ul className="px-3 pb-3">
            {otherPeople.map((person) => (
              <UserRow key={person.id} user={person} onSelect={open} />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
