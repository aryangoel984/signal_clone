import { Avatar } from "@/components/Avatar";
import type { UserPublic } from "@/types/contact";

/** A person in the compose panel or search results; clicking opens the DM. */
export function UserRow({ user, onSelect }: { user: UserPublic; onSelect: (user: UserPublic) => void }) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(user)}
        className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left hover:bg-selected"
      >
        <Avatar name={user.name} color={user.avatar_color} imageUrl={user.avatar_url} size={32} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm text-text-primary">{user.name}</span>
          {user.username && <span className="block truncate text-xs text-text-secondary">@{user.username}</span>}
        </span>
      </button>
    </li>
  );
}

export function SectionHeading({ children }: { children: string }) {
  return <h2 className="px-4 pt-4 pb-1 text-sm font-semibold text-text-primary">{children}</h2>;
}
