"use client";

import { Settings } from "lucide-react";

import { Avatar } from "@/components/Avatar";
import { Button } from "@/components/Button";
import { SectionPlaceholder } from "@/features/shell/SectionPlaceholder";
import { useAuthStore } from "@/store/auth";

// Placeholder until the settings pages in phase 7: profile summary and Log out.
export default function SettingsPage() {
  const user = useAuthStore((state) => state.user);
  const signOut = useAuthStore((state) => state.signOut);

  return (
    <SectionPlaceholder
      title="Settings"
      icon={Settings}
      message="Privacy, notifications and appearance settings are coming soon."
      sidebar={
        user && (
          <div className="flex flex-col gap-4 px-4">
            <div className="flex items-center gap-3">
              <Avatar name={user.display_name} color={user.avatar_color} imageUrl={user.avatar_url} size={48} />
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-text-primary">{user.display_name}</p>
                <p className="truncate text-sm text-text-secondary">{user.phone_number}</p>
              </div>
            </div>
            <Button variant="secondary" className="self-start" onClick={() => void signOut()}>
              Log out
            </Button>
          </div>
        )
      }
    />
  );
}
