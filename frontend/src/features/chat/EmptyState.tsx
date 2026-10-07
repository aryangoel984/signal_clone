import { SignalLogo } from "@/components/SignalLogo";

/** Shown in the main pane when no conversation is selected. */
export function EmptyState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 bg-chat">
      <SignalLogo size={88} />
      <h2 className="text-xl font-semibold text-text-primary">Welcome to Signal</h2>
      <p className="text-sm text-text-secondary">Select a chat or start a new one with the ✎ button.</p>
    </div>
  );
}
