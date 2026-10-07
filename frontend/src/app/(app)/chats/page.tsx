"use client";

// Temporary phase-2 landing page so login, reload and logout can be tested end to end.
// Replaced by the real chat list in phase 3.

import { Avatar } from "@/components/Avatar";
import { Button } from "@/components/Button";
import { useAuthStore } from "@/store/auth";

export default function ChatsPage() {
  const user = useAuthStore((state) => state.user);
  const signOut = useAuthStore((state) => state.signOut);
  if (!user) return null;

  return (
    <main className="flex flex-1 items-center justify-center bg-chat p-4">
      <section className="flex w-full max-w-sm flex-col items-center rounded-card border border-border-card bg-card p-6 text-center">
        <Avatar name={user.display_name} color={user.avatar_color} imageUrl={user.avatar_url} size={80} />
        <h1 className="mt-4 text-lg font-semibold text-text-primary">{user.display_name}</h1>
        <p className="text-sm text-text-secondary">{user.phone_number}</p>
        <p className="mt-4 text-sm text-text-muted">The chat list arrives in phase 3.</p>
        <Button variant="secondary" className="mt-6" onClick={() => void signOut()}>
          Log out
        </Button>
      </section>
    </main>
  );
}
