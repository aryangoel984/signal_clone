"use client";

import { type FormEvent, type ReactNode, useState } from "react";

import { inputClassName } from "@/features/auth/AuthScreen";
import { apiRequest } from "@/lib/api";
import { COUNTRIES, toE164 } from "@/lib/phone";
import { useLeftPane } from "@/store/left-pane";
import { showToast } from "@/store/toasts";
import type { UserPublic } from "@/types/contact";

import { PaneHeader } from "./PaneHeader";
import { useOpenDirect } from "./useOpenDirect";

function FindForm({
  title,
  children,
  canSubmit,
  onSubmit,
}: {
  title: string;
  children: ReactNode;
  canSubmit: boolean;
  onSubmit: () => Promise<void>;
}) {
  const setMode = useLeftPane((state) => state.setMode);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    await onSubmit();
    setBusy(false);
  }

  return (
    <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
      <PaneHeader title={title} onBack={() => setMode("compose")} />
      <div className="flex-1 px-4 pt-2">{children}</div>
      <div className="flex justify-end p-3">
        <button
          type="submit"
          disabled={!canSubmit || busy}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-on-accent hover:brightness-110 disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </form>
  );
}

async function findExact(query: string, matches: (user: UserPublic) => boolean): Promise<UserPublic | undefined> {
  const users = await apiRequest<UserPublic[]>(`/users/search?q=${encodeURIComponent(query)}`);
  return users.find(matches);
}

export function FindByUsernamePanel() {
  const openDirect = useOpenDirect();
  const [username, setUsername] = useState("");
  const wanted = username.trim().replace(/^@/, "").toLowerCase();

  return (
    <FindForm
      title="Find by username"
      canSubmit={wanted.length >= 3}
      onSubmit={async () => {
        const user = await findExact(wanted, (candidate) => candidate.username === wanted);
        if (user) await openDirect(user.id);
        else showToast(`@${wanted} is not a Signal user. Make sure you've entered the complete username.`);
      }}
    >
      <input
        autoFocus
        value={username}
        onChange={(event) => setUsername(event.target.value)}
        placeholder="Username"
        aria-label="Username"
        className={inputClassName}
      />
      <p className="mt-3 text-xs text-text-primary">Enter a username followed by a dot and its set of numbers.</p>
    </FindForm>
  );
}

export function FindByPhonePanel() {
  const openDirect = useOpenDirect();
  const [countryCode, setCountryCode] = useState("US");
  const [national, setNational] = useState("");
  const dial = COUNTRIES.find((country) => country.code === countryCode)?.dial ?? "1";
  const phone = toE164(dial, national);

  return (
    <FindForm
      title="Find by phone number"
      canSubmit={phone !== null}
      onSubmit={async () => {
        if (!phone) return;
        // For a full E.164 query the backend only returns exact phone matches (non-contacts'
        // numbers are hidden in the response, so they can't be compared here).
        const user = await findExact(phone, () => true);
        if (user) await openDirect(user.id);
        else showToast(`${phone} is not a Signal user.`);
      }}
    >
      <select
        value={countryCode}
        onChange={(event) => setCountryCode(event.target.value)}
        aria-label="Country"
        className={inputClassName}
      >
        {COUNTRIES.map((country) => (
          <option key={country.code} value={country.code}>
            {country.name} (+{country.dial})
          </option>
        ))}
      </select>
      <input
        autoFocus
        type="tel"
        value={national}
        onChange={(event) => setNational(event.target.value)}
        placeholder="Phone number"
        aria-label="Phone number"
        className={`${inputClassName} mt-2`}
      />
    </FindForm>
  );
}
