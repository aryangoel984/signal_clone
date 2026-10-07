import { ChevronRight, UserRoundX, Users } from "lucide-react";

import { Avatar } from "@/components/Avatar";
import type { ConversationDetail } from "@/types/conversation";

function firstName(name: string): string {
  return name.split(" ")[0] ?? name;
}

/** "Priya, Marcus and you" / "Priya, Marcus, Sofia and 1 other" / "... and 2 others". */
export function groupMembersLine(conversation: ConversationDetail): string {
  const others = conversation.members.filter((member) => member.name !== "You").map((member) => firstName(member.name));
  if (others.length === 0) return "Only you";
  if (others.length <= 3) return `${others.join(", ")} and you`;
  const rest = others.length - 3;
  return `${others.slice(0, 3).join(", ")} and ${rest} ${rest === 1 ? "other" : "others"}`;
}

function groupsInCommonLine(groups: string[]) {
  if (groups.length === 0) return <>No groups in common</>;
  if (groups.length === 1) return <>Member of <strong className="font-semibold">{groups[0]}</strong></>;
  return (
    <>
      Member of <strong className="font-semibold">{groups[0]}</strong> and {groups.length - 1} other
      {groups.length > 2 ? "s" : ""}
    </>
  );
}

/** The card at the top of a conversation: big avatar, name, and a line of context. */
export function ConversationHero({ conversation }: { conversation: ConversationDetail }) {
  const isGroup = conversation.type === "group";
  return (
    <div className="flex flex-col items-center pt-8">
      <div className="relative z-10">
        <Avatar
          name={conversation.title}
          color={conversation.avatar_color}
          imageUrl={conversation.avatar_url}
          size={72}
          isGroup={isGroup}
        />
      </div>
      <div className="-mt-[38px] flex min-w-64 flex-col items-center gap-2 rounded-[22px] border border-border-card px-8 pt-12 pb-5">
        <h2 className="flex items-center gap-0.5 text-xl font-semibold text-text-primary">
          {conversation.title}
          {!isGroup && <ChevronRight size={20} strokeWidth={2} aria-hidden />}
        </h2>
        {!isGroup && conversation.is_contact === false && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-warning-bg px-2.5 py-1 text-[13px] font-medium text-warning">
            <UserRoundX size={14} strokeWidth={2} aria-hidden />
            Name not verified
          </span>
        )}
        <p className="flex items-center gap-1.5 text-[13px] text-text-primary">
          <Users size={14} strokeWidth={1.75} aria-hidden />
          {/* one span, so the flex gap only separates the icon from the text */}
          <span>{isGroup ? groupMembersLine(conversation) : groupsInCommonLine(conversation.groups_in_common)}</span>
        </p>
      </div>
    </div>
  );
}
