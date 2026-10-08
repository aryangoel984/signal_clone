"use client";

import { Ellipsis, Plus, SquareStack } from "lucide-react";
import { useState } from "react";

import { Avatar } from "@/components/Avatar";
import { IconButton } from "@/components/IconButton";
import { SearchField } from "@/features/conversations/PaneHeader";
import { SectionPlaceholder } from "@/features/shell/SectionPlaceholder";
import { useAuthStore } from "@/store/auth";
import { COMING_SOON, showToast } from "@/store/toasts";

const soon = () => showToast(COMING_SOON);

export default function StoriesPage() {
  const user = useAuthStore((state) => state.user);
  const [query, setQuery] = useState("");
  return (
    <SectionPlaceholder
      title="Stories"
      actions={
        <>
          <IconButton icon={Plus} label="Add a story" onClick={soon} />
          <IconButton icon={Ellipsis} label="More" onClick={soon} />
        </>
      }
      sidebar={
        <>
          <SearchField value={query} onChange={setQuery} placeholder="Search" />
          <button type="button" onClick={soon} className="mx-3 flex items-center gap-3 rounded-lg px-2 py-2.5 text-left hover:bg-selected">
            <span className="relative">
              <Avatar name={user?.display_name ?? null} color={user?.avatar_color ?? "A210"} imageUrl={user?.avatar_url} size={48} />
              <span className="absolute -right-0.5 -bottom-0.5 flex h-[18px] w-[18px] items-center justify-center rounded-full border-2 border-sidebar bg-primary text-on-primary">
                <Plus size={11} strokeWidth={3} aria-hidden />
              </span>
            </span>
            <span>
              <span className="block text-sm font-semibold text-text-primary">My Story</span>
              <span className="block text-sm text-text-secondary">Add a story</span>
            </span>
          </button>
          <div className="flex flex-1 flex-col items-center justify-center pb-24 text-center">
            <p className="text-base font-semibold text-text-primary">No stories</p>
            <p className="mt-1 text-sm text-text-secondary">New updates will appear here.</p>
          </div>
        </>
      }
      emptyState={
        <>
          <SquareStack size={32} strokeWidth={1.5} aria-hidden />
          <p className="flex items-center gap-1 text-sm">
            Click <Plus size={15} aria-label="plus" /> to add an update.
          </p>
        </>
      }
    />
  );
}
