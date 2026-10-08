import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Toggle } from "@/components/Toggle";

/** Page frame: centered title and a column of cards, like Signal Desktop's settings. */
export function SettingsPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto bg-chat">
      <div className="mx-auto w-full max-w-[720px] px-4 pt-4 pb-12 pane:px-6 pane:pt-10">
        <div className="relative mb-8 flex items-center justify-center">
          <Link href="/settings" aria-label="Back to settings" className="absolute left-0 rounded-control p-1.5 text-text-primary hover:bg-selected pane:hidden">
            <ChevronLeft size={20} aria-hidden />
          </Link>
          <h1 className="text-[15px] font-semibold text-text-primary">{title}</h1>
        </div>
        <div className="flex flex-col gap-6">{children}</div>
      </div>
    </div>
  );
}

export function SettingsSection({ title, note, children }: { title?: string; note?: string; children: ReactNode }) {
  return (
    <section>
      {title && <h2 className="mb-2 px-1 text-sm font-semibold text-text-primary">{title}</h2>}
      <div className="rounded-[18px] border border-border-card bg-card px-6 py-2">{children}</div>
      {note && <p className="mt-2 px-4 text-[13px] text-text-secondary">{note}</p>}
    </section>
  );
}

export function SettingsRow({ label, description, children }: { label: string; description?: string; children?: ReactNode }) {
  return (
    <div className="flex items-center gap-4 py-2.5">
      <div className="min-w-0 flex-1">
        <p className="text-sm text-text-primary">{label}</p>
        {description && <p className="mt-0.5 text-[13px] text-text-secondary">{description}</p>}
      </div>
      {children}
    </div>
  );
}

export function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <SettingsRow label={label} description={description}>
      <Toggle checked={checked} onChange={onChange} label={label} />
    </SettingsRow>
  );
}
