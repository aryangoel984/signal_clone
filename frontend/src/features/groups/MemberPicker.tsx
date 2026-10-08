"use client";

import { Check, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Avatar } from "@/components/Avatar";
import { SearchField } from "@/features/conversations/PaneHeader";
import { useUserSearch } from "@/features/conversations/useUserSearch";
import { apiRequest } from "@/lib/api";
import type { UserPublic } from "@/types/contact";

type MemberPickerProps = {
  selected: UserPublic[];
  onChange: (selected: UserPublic[]) => void;
  excludeIds?: number[]; // e.g. people already in the group
};

/** "Choose members": search box, chips for picked people, contacts with round checkboxes. */
export function MemberPicker({ selected, onChange, excludeIds = [] }: MemberPickerProps) {
  const [query, setQuery] = useState("");
  const [contacts, setContacts] = useState<UserPublic[] | null>(null);
  const results = useUserSearch(query);

  useEffect(() => {
    apiRequest<UserPublic[]>("/contacts").then(setContacts).catch(() => setContacts([]));
  }, []);

  const pickedIds = new Set(selected.map((person) => person.id));
  const people = (query.trim() ? results : contacts)?.filter((person) => !excludeIds.includes(person.id)) ?? null;
  const toggle = (person: UserPublic) =>
    onChange(pickedIds.has(person.id) ? selected.filter((p) => p.id !== person.id) : [...selected, person]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <SearchField value={query} onChange={setQuery} placeholder="Name, username, or number" autoFocus />
      {selected.length > 0 && (
        <ul className="flex flex-wrap gap-2 px-4 pb-2" aria-label="Selected">
          {selected.map((person) => (
            <li key={person.id} className="flex items-center gap-1.5 rounded-md bg-search py-1 pr-1.5 pl-1">
              <Avatar name={person.name} color={person.avatar_color} imageUrl={person.avatar_url} size={20} />
              <span className="text-sm text-text-primary">{person.name.split(" ")[0]}</span>
              <button type="button" aria-label={`Remove ${person.name}`} onClick={() => toggle(person)} className="text-text-secondary">
                <X size={14} aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      <h2 className="px-4 pt-2 pb-1 text-sm font-semibold text-text-primary">Contacts</h2>
      <ul className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {people?.length === 0 && <li className="px-1 py-2 text-sm text-text-secondary">No results</li>}
        {people?.map((person) => {
          const picked = pickedIds.has(person.id);
          return (
            <li key={person.id}>
              <button
                type="button"
                role="checkbox"
                aria-checked={picked}
                onClick={() => toggle(person)}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left hover:bg-selected ${picked ? "bg-selected" : ""}`}
              >
                <Avatar name={person.name} color={person.avatar_color} imageUrl={person.avatar_url} size={32} />
                <span className="min-w-0 flex-1 truncate text-sm text-text-primary">{person.name}</span>
                <span
                  aria-hidden
                  className={`flex h-5 w-5 items-center justify-center rounded-full border ${
                    picked ? "border-primary bg-primary text-on-primary" : "border-text-muted"
                  }`}
                >
                  {picked && <Check size={13} strokeWidth={3} />}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
