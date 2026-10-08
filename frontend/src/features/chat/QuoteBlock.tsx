import type { Quote } from "@/types/message";

type QuoteBlockProps = {
  quote: Quote | null; // null: the original isn't visible to me
  /** Where it's drawn: inside my (blue) bubble, inside an incoming bubble, or above the composer. */
  tone: "outgoing" | "incoming" | "composer";
  onClick?: () => void;
};

const TONES = {
  outgoing: "bg-quote-outgoing border-on-bubble-outgoing text-on-bubble-outgoing",
  incoming: "bg-quote-incoming border-primary text-on-bubble-incoming",
  composer: "bg-composer border-primary text-text-primary",
} as const;

/** Signal's quoted-message panel: a coloured bar, the author, and up to two lines of text. */
export function QuoteBlock({ quote, tone, onClick }: QuoteBlockProps) {
  const className = `block w-full min-w-0 rounded-[10px] border-l-4 px-2.5 py-1.5 text-left text-[13px] leading-[18px] ${TONES[tone]}`;
  if (quote === null) {
    return <div className={`${className} italic opacity-80`}>Original message not found</div>;
  }
  const content = (
    <>
      <span className="block font-semibold">{quote.author_name}</span>
      <span className="line-clamp-2 break-words whitespace-pre-wrap opacity-90">{quote.text}</span>
    </>
  );
  if (!onClick) return <div className={className}>{content}</div>;
  return (
    <button type="button" onClick={onClick} className={`${className} cursor-pointer hover:brightness-95`} aria-label={`Go to the message from ${quote.author_name}`}>
      {content}
    </button>
  );
}
