import type { Reaction } from "@/types/message";

type ReactionPillsProps = {
  reactions: Reaction[];
  myId: number;
  onToggle: (emoji: string) => void; // set this emoji as mine, or remove it if it already is
};

type Pill = { emoji: string; count: number; mine: boolean };

/** One pill per emoji, in the order they were first used. */
function groupByEmoji(reactions: Reaction[], myId: number): Pill[] {
  const pills = new Map<string, Pill>();
  for (const { emoji, user_id } of reactions) {
    const pill = pills.get(emoji) ?? { emoji, count: 0, mine: false };
    pill.count += 1;
    pill.mine ||= user_id === myId;
    pills.set(emoji, pill);
  }
  return [...pills.values()];
}

export function ReactionPills({ reactions, myId, onToggle }: ReactionPillsProps) {
  if (reactions.length === 0) return null;
  return (
    <div className="relative z-[1] -mt-1.5 flex flex-wrap gap-1 px-2">
      {groupByEmoji(reactions, myId).map(({ emoji, count, mine }) => (
        <button
          key={emoji}
          type="button"
          onClick={() => onToggle(emoji)}
          aria-pressed={mine}
          aria-label={`${emoji} ${count}${mine ? ", including you" : ""}`}
          className={`flex h-6 items-center gap-1 rounded-full border border-chat px-1.5 text-[13px] leading-none text-text-primary shadow-sm ${
            mine ? "bg-reaction-pill-mine" : "bg-reaction-pill"
          }`}
        >
          <span className="text-[14px]">{emoji}</span>
          {count > 1 && <span className="text-xs text-text-secondary">{count}</span>}
        </button>
      ))}
    </div>
  );
}
