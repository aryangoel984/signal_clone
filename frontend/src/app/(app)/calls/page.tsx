"use client";

import { Ellipsis, Link as LinkIcon, ListFilter, Phone, PhoneCall } from "lucide-react";
import { useState } from "react";

import { IconButton } from "@/components/IconButton";
import { SearchField } from "@/features/conversations/PaneHeader";
import { SectionPlaceholder } from "@/features/shell/SectionPlaceholder";
import { COMING_SOON, showToast } from "@/store/toasts";

const soon = () => showToast(COMING_SOON);

export default function CallsPage() {
  const [query, setQuery] = useState("");
  return (
    <SectionPlaceholder
      title="Calls"
      actions={
        <>
          <IconButton icon={PhoneCall} label="New call" onClick={soon} />
          <IconButton icon={Ellipsis} label="More" onClick={soon} />
        </>
      }
      sidebar={
        <>
          <SearchField value={query} onChange={setQuery} placeholder="Search" trailing={<IconButton icon={ListFilter} label="Filter calls" onClick={soon} />} />
          <ul className="px-3">
            <li>
              <button type="button" onClick={soon} className="flex w-full items-center gap-3 rounded-lg px-3.5 py-3 text-left hover:bg-selected">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-search text-text-primary">
                  <LinkIcon size={18} strokeWidth={1.75} aria-hidden />
                </span>
                <span className="text-sm text-text-primary">Create a Call Link</span>
              </button>
            </li>
          </ul>
        </>
      }
      emptyState={
        <>
          <Phone size={32} strokeWidth={1.5} aria-hidden />
          <p className="flex items-center gap-1 text-sm">
            Click <PhoneCall size={15} aria-label="new call" /> to start a new voice or video call.
          </p>
        </>
      }
    />
  );
}
