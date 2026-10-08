"use client";

import { AtSign, Hash, type LucideIcon, Users } from "lucide-react";
import { useEffect, useState } from "react";

import { apiRequest } from "@/lib/api";
import { useLeftPane } from "@/store/left-pane";
import { showToast } from "@/store/toasts";
import type { UserPublic } from "@/types/contact";

import { PaneHeader, SearchField } from "./PaneHeader";
import { useOpenDirect } from "./useOpenDirect";
import { useUserSearch } from "./useUserSearch";
import { SectionHeading, UserRow } from "./UserRow";

function ActionRow({ icon: Icon, label, onClick }: { icon: LucideIcon; label: string; onClick: () => void }) {
  return (
    <li>
      <button type="button" onClick={onClick} className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left hover:bg-selected">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-search text-text-primary">
          <Icon size={16} strokeWidth={1.75} aria-hidden />
        </span>
        <span className="text-sm text-text-primary">{label}</span>
      </button>
    </li>
  );
}

/** "New chat": replaces the chat list. Shows actions and contacts, or search results while typing. */
export function ComposePanel() {
  const setMode = useLeftPane((state) => state.setMode);
  const openDirect = useOpenDirect();
  const [query, setQuery] = useState("");
  const [contacts, setContacts] = useState<UserPublic[] | null>(null);
  const results = useUserSearch(query);

  useEffect(() => {
    apiRequest<UserPublic[]>("/contacts")
      .then(setContacts)
      .catch(() => showToast("Couldn't load contacts"));
  }, []);

  const searching = query.trim() !== "";
  const people = searching ? results : contacts;

  return (
    <>
      <PaneHeader title="New chat" onBack={() => setMode("chats")} />
      <SearchField value={query} onChange={setQuery} placeholder="Name, username, or number" autoFocus />
      <div className="min-h-0 flex-1 overflow-y-auto">
        {!searching && (
          <ul className="px-3 pt-1">
            <ActionRow icon={Users} label="New group" onClick={() => setMode("newGroup")} />
            <ActionRow icon={AtSign} label="Find by username" onClick={() => setMode("findUsername")} />
            <ActionRow icon={Hash} label="Find by phone number" onClick={() => setMode("findPhone")} />
          </ul>
        )}
        <SectionHeading>Contacts</SectionHeading>
        {people && people.length === 0 && (
          <p className="px-4 py-2 text-sm text-text-secondary">{searching ? `No results for "${query.trim()}"` : "No contacts yet"}</p>
        )}
        <ul className="px-3 pb-3">
          {people?.map((person) => (
            <UserRow key={person.id} user={person} onSelect={(user) => void openDirect(user.id)} />
          ))}
        </ul>
      </div>
    </>
  );
}
