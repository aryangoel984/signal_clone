import { Avatar } from "@/components/Avatar";
import { TypingDots } from "@/components/TypingDots";
import type { Member } from "@/types/conversation";

/** Incoming-style bubble with animated dots; in groups, the typists' avatars beside it. */
export function TypingIndicator({ members }: { members: Member[] }) {
  const who = members.map((member) => member.name).join(", ");
  const label = members.length === 0 ? "Typing" : `${who} ${members.length === 1 ? "is" : "are"} typing`;
  return (
    <div className="mt-3 flex items-end gap-2" aria-live="polite" aria-label={label} title={label}>
      {members.length > 0 && (
        <span className="flex -space-x-2">
          {members.slice(0, 3).map((member) => (
            <Avatar key={member.user_id} name={member.name} color={member.avatar_color} imageUrl={member.avatar_url} size={28} />
          ))}
        </span>
      )}
      <div className="rounded-[18px] bg-bubble-incoming px-3.5 py-3 text-text-secondary">
        <TypingDots />
      </div>
    </div>
  );
}
