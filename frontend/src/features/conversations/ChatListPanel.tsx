"use client";

import { Archive, Ellipsis, FolderPlus, ListFilter, Moon, SquarePen } from "lucide-react";
import { useEffect, useState } from "react";

import { IconButton } from "@/components/IconButton";
import { belowElement, Menu, type MenuPosition } from "@/components/Menu";
import { useConversations } from "@/store/conversations";
import { useLeftPane } from "@/store/left-pane";
import { COMING_SOON, showToast } from "@/store/toasts";

import { ConversationList } from "./ConversationList";
import { SearchField } from "./PaneHeader";
import { SearchResults } from "./SearchResults";

/** The default left pane: "Chats" header, search + unread filter, and the chat list. */
export function ChatListPanel() {
  const chats = useConversations((state) => state.chats);
  const loadChats = useConversations((state) => state.loadChats);
  const { query, setQuery, unreadOnly, toggleUnreadOnly, setMode } = useLeftPane();
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null);

  useEffect(() => {
    loadChats().catch(() => showToast("Couldn't load chats"));
  }, [loadChats]);

  const visible = unreadOnly ? (chats ?? []).filter((chat) => chat.unread_count > 0) : (chats ?? []);

  return (
    <>
      <header className="flex h-[52px] shrink-0 items-center gap-1 pr-3 pl-4">
        <h1 className="flex-1 text-xl font-semibold text-text-primary">Chats</h1>
        <IconButton icon={SquarePen} label="New chat" onClick={() => setMode("compose")} />
        <IconButton
          icon={Ellipsis}
          label="More"
          onClick={(event) => setMenuPosition(belowElement(event.currentTarget))}
        />
      </header>
      <SearchField
        value={query}
        onChange={setQuery}
        placeholder="Search"
        trailing={
          <IconButton
            icon={ListFilter}
            label={unreadOnly ? "Show all chats" : "Show unread chats only"}
            active={unreadOnly}
            onClick={toggleUnreadOnly}
          />
        }
      />
      <div className="min-h-0 flex-1 overflow-y-auto">
        {chats === null ? null : query.trim() ? (
          <SearchResults chats={visible} query={query} />
        ) : (
          <ConversationList chats={visible} emptyText={unreadOnly ? "No unread chats" : "No chats yet"} />
        )}
      </div>
      {menuPosition && (
        <Menu
          position={menuPosition}
          onClose={() => setMenuPosition(null)}
          items={[
            { label: "View Archive", icon: Archive, onSelect: () => setMode("archive") },
            { label: "Add chat folder", icon: FolderPlus, onSelect: () => showToast(COMING_SOON) },
            { label: "Notification profile", icon: Moon, onSelect: () => showToast(COMING_SOON) },
          ]}
        />
      )}
    </>
  );
}
