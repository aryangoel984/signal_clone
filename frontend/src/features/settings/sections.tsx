"use client";

import { useEffect, useState } from "react";

import { Avatar } from "@/components/Avatar";
import { Button } from "@/components/Button";
import { inputClassName } from "@/features/auth/AuthScreen";
import { ApiError, apiRequest } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { useConversations } from "@/store/conversations";
import { useSettings } from "@/store/settings";
import { showToast } from "@/store/toasts";
import type { UserPublic } from "@/types/contact";
import type { Settings, Theme } from "@/types/settings";
import type { Me } from "@/types/user";

import { SettingsPage, SettingsRow, SettingsSection, ToggleRow } from "./SettingsUI";

function useSetting(): [Settings | null, (changes: Partial<Settings>) => void] {
  const settings = useSettings((state) => state.settings);
  const update = useSettings((state) => state.update);
  return [settings, (changes) => void update(changes).catch(() => showToast("Couldn't save the setting"))];
}

function ComingSoonCard() {
  return (
    <SettingsSection>
      <SettingsRow label="Coming soon" description="This section isn't available in the web clone yet." />
    </SettingsSection>
  );
}

function ProfilePage() {
  const user = useAuthStore((state) => state.user);
  const setUser = useAuthStore((state) => state.setUser);
  const [name, setName] = useState(user?.display_name ?? "");
  const [about, setAbout] = useState(user?.about ?? "");
  if (!user) return null;

  async function save() {
    try {
      setUser(await apiRequest<Me>("/users/me", { method: "PATCH", body: { display_name: name, about } }));
      showToast("Profile saved");
    } catch (error) {
      showToast(error instanceof ApiError ? error.detail : "Couldn't save");
    }
  }

  return (
    <SettingsPage title="Profile">
      <div className="flex justify-center">
        <Avatar name={user.display_name} color={user.avatar_color} imageUrl={user.avatar_url} size={80} />
      </div>
      <SettingsSection>
        <label className="block py-2 text-[13px] text-text-secondary">
          Name
          <input value={name} maxLength={64} onChange={(e) => setName(e.target.value)} className={`${inputClassName} mt-1`} />
        </label>
        <label className="block py-2 text-[13px] text-text-secondary">
          About
          <input value={about} maxLength={140} onChange={(e) => setAbout(e.target.value)} className={`${inputClassName} mt-1`} />
        </label>
        <div className="flex justify-end py-2">
          <Button onClick={() => void save()} disabled={!name.trim()}>
            Save
          </Button>
        </div>
      </SettingsSection>
    </SettingsPage>
  );
}

function AccountPage() {
  const user = useAuthStore((state) => state.user);
  const signOut = useAuthStore((state) => state.signOut);
  return (
    <SettingsPage title="Account">
      <SettingsSection note="Signal Desktop is a linked device; linking more devices isn't available here.">
        <SettingsRow label="Phone number" description={user?.phone_number} />
        <SettingsRow label="Linked devices" description="Link Signal on other computers and tablets.">
          <Button variant="secondary" onClick={() => showToast("Coming soon")}>
            Link new device
          </Button>
        </SettingsRow>
      </SettingsSection>
      <SettingsSection>
        <SettingsRow label="Log out" description="You can log back in with your phone number and the code 123456.">
          <Button variant="secondary" className="!text-danger" onClick={() => void signOut()}>
            Log out
          </Button>
        </SettingsRow>
      </SettingsSection>
    </SettingsPage>
  );
}

function GeneralPage() {
  const user = useAuthStore((state) => state.user);
  return (
    <SettingsPage title="General">
      <SettingsSection note="To change the name of this device, open Signal on your phone and navigate to Settings > Linked devices">
        <SettingsRow label="Phone Number">
          <span className="text-sm text-text-secondary">{user?.phone_number}</span>
        </SettingsRow>
        <SettingsRow label="Device Name">
          <span className="text-sm text-text-secondary">Web</span>
        </SettingsRow>
      </SettingsSection>
    </SettingsPage>
  );
}

const THEMES: { value: Theme; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

function AppearancePage() {
  const [settings, update] = useSetting();
  return (
    <SettingsPage title="Appearance">
      <SettingsSection>
        <SettingsRow label="Theme">
          <select
            aria-label="Theme"
            value={settings?.theme ?? "system"}
            onChange={(event) => update({ theme: event.target.value as Theme })}
            className="rounded-full border border-border-card bg-button-secondary px-3 py-1.5 text-sm text-text-primary"
          >
            {THEMES.map((theme) => (
              <option key={theme.value} value={theme.value}>
                {theme.label}
              </option>
            ))}
          </select>
        </SettingsRow>
      </SettingsSection>
    </SettingsPage>
  );
}

function ChatsPage() {
  const [settings, update] = useSetting();
  return (
    <SettingsPage title="Chats">
      <SettingsSection title="Text input">
        <ToggleRow
          label="Enter key sends"
          description="When off, Enter adds a new line and Ctrl/⌘+Enter sends."
          checked={settings?.enter_key_sends ?? true}
          onChange={(value) => update({ enter_key_sends: value })}
        />
      </SettingsSection>
    </SettingsPage>
  );
}

function NotificationsPage() {
  const [settings, update] = useSetting();
  return (
    <SettingsPage title="Notifications">
      <SettingsSection note="Shows a notice when a message arrives in a chat that isn't open. Muted chats stay quiet.">
        <ToggleRow
          label="Enable notifications"
          checked={settings?.notifications_enabled ?? true}
          onChange={(value) => update({ notifications_enabled: value })}
        />
      </SettingsSection>
    </SettingsPage>
  );
}

function PrivacyPage() {
  const [settings, update] = useSetting();
  const refreshChats = useConversations((state) => state.refreshSoon);
  const [blocked, setBlocked] = useState<UserPublic[] | null>(null);

  useEffect(() => {
    apiRequest<UserPublic[]>("/blocks").then(setBlocked).catch(() => setBlocked([]));
  }, []);

  async function unblock(person: UserPublic) {
    try {
      await apiRequest<void>(`/blocks/${person.id}`, { method: "DELETE" });
      setBlocked((current) => current?.filter((p) => p.id !== person.id) ?? null);
      refreshChats();
      showToast(`${person.name} unblocked`);
    } catch {
      showToast("Couldn't unblock");
    }
  }

  return (
    <SettingsPage title="Privacy">
      <SettingsSection
        title="Messaging"
        note="See and share when messages are being read and typed. If disabled, you won't see read receipts or typing indicators from others."
      >
        <ToggleRow
          label="Read receipts"
          checked={settings?.read_receipts_enabled ?? true}
          onChange={(value) => update({ read_receipts_enabled: value })}
        />
        <ToggleRow
          label="Typing indicators"
          checked={settings?.typing_indicators_enabled ?? true}
          onChange={(value) => update({ typing_indicators_enabled: value })}
        />
      </SettingsSection>
      <SettingsSection title="Blocked">
        {blocked?.length === 0 && <SettingsRow label="No blocked users" />}
        {blocked?.map((person) => (
          <div key={person.id} className="flex items-center gap-3 py-2">
            <Avatar name={person.name} color={person.avatar_color} imageUrl={person.avatar_url} size={32} />
            <span className="min-w-0 flex-1 truncate text-sm text-text-primary">{person.name}</span>
            <Button variant="secondary" onClick={() => void unblock(person)}>
              Unblock
            </Button>
          </div>
        ))}
      </SettingsSection>
    </SettingsPage>
  );
}

function placeholder(title: string) {
  return function Placeholder() {
    return (
      <SettingsPage title={title}>
        <ComingSoonCard />
      </SettingsPage>
    );
  };
}

export const SETTINGS_SECTIONS: Record<string, () => React.JSX.Element | null> = {
  profile: ProfilePage,
  account: AccountPage,
  general: GeneralPage,
  appearance: AppearancePage,
  chats: ChatsPage,
  calls: placeholder("Calls"),
  notifications: NotificationsPage,
  privacy: PrivacyPage,
  "data-usage": placeholder("Data usage"),
  backups: placeholder("Backups"),
};
