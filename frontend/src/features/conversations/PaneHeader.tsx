import { ChevronLeft } from "lucide-react";
import type { ReactNode } from "react";

import { IconButton } from "@/components/IconButton";

/** "‹  Title" header used by the panels that replace the chat list (New chat, Archive, Find by …). */
export function PaneHeader({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <header className="relative flex h-[52px] shrink-0 items-center justify-center px-3">
      <IconButton icon={ChevronLeft} label="Back" onClick={onBack} className="absolute left-3" />
      <h1 className="text-[15px] font-semibold text-text-primary">{title}</h1>
    </header>
  );
}

export function SearchField({
  value,
  onChange,
  placeholder,
  trailing,
  autoFocus = false,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  trailing?: ReactNode;
  autoFocus?: boolean;
}) {
  return (
    <div className="flex items-center gap-2 px-4 pb-2">
      <label className="flex h-7 min-w-0 flex-1 items-center gap-2 rounded-md bg-search px-2.5 focus-within:ring-2 focus-within:ring-accent">
        <SearchIcon />
        <input
          type="search"
          value={value}
          autoFocus={autoFocus}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          aria-label={placeholder}
          className="min-w-0 flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted [&::-webkit-search-cancel-button]:hidden"
        />
        {value && (
          <button type="button" aria-label="Clear search" onClick={() => onChange("")} className="text-text-secondary">
            <CloseIcon />
          </button>
        )}
      </label>
      {trailing}
    </div>
  );
}

function SearchIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 text-text-secondary" aria-hidden>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" strokeLinecap="round" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
    </svg>
  );
}
