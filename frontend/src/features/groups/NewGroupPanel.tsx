"use client";

import { Camera, ChevronDown, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { type ChangeEvent, useEffect, useRef, useState } from "react";

import { Avatar } from "@/components/Avatar";
import { inputClassName } from "@/features/auth/AuthScreen";
import { PaneHeader } from "@/features/conversations/PaneHeader";
import { ApiError, apiRequest } from "@/lib/api";
import { downscaleAvatar } from "@/lib/image";
import { useConversations } from "@/store/conversations";
import { useLeftPane } from "@/store/left-pane";
import { COMING_SOON, showToast } from "@/store/toasts";
import type { UserPublic } from "@/types/contact";
import type { ConversationDetail } from "@/types/conversation";

import { MemberPicker } from "./MemberPicker";

const MAX_NAME = 32;

function AccentButton({ label, disabled, onClick }: { label: string; disabled: boolean; onClick: () => void }) {
  return (
    <div className="flex justify-end p-3">
      <button
        type="button"
        disabled={disabled}
        onClick={onClick}
        className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-on-accent hover:brightness-110 disabled:opacity-50"
      >
        {label}
      </button>
    </div>
  );
}

/** Two steps in the left pane, as in Signal: "Choose members", then "Name this group". */
export function NewGroupPanel() {
  const router = useRouter();
  const setMode = useLeftPane((state) => state.setMode);
  const loadChats = useConversations((state) => state.loadChats);
  const [step, setStep] = useState<"members" | "name">("members");
  const [members, setMembers] = useState<UserPublic[]>([]);
  const [name, setName] = useState("");
  const [photo, setPhoto] = useState<Blob | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  async function pickPhoto(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const scaled = await downscaleAvatar(file);
      setPhoto(scaled);
      setPreview(URL.createObjectURL(scaled));
    } catch {
      showToast("That image couldn't be read");
    }
  }

  async function create() {
    setCreating(true);
    try {
      let group = await apiRequest<ConversationDetail>("/groups", {
        method: "POST",
        body: { name, member_ids: members.map((member) => member.id) },
      });
      if (photo) {
        const form = new FormData();
        form.append("file", photo, "group.jpg");
        group = await apiRequest<ConversationDetail>(`/groups/${group.id}/avatar`, { method: "PUT", body: form });
      }
      await loadChats();
      setMode("chats");
      router.push(`/chats/${group.id}`);
    } catch (error) {
      showToast(error instanceof ApiError ? error.detail : "Couldn't create the group");
      setCreating(false);
    }
  }

  if (step === "members") {
    return (
      <>
        <PaneHeader title="Choose members" onBack={() => setMode("compose")} />
        <MemberPicker selected={members} onChange={setMembers} />
        <AccentButton label="Next" disabled={members.length === 0} onClick={() => setStep("name")} />
      </>
    );
  }

  return (
    <>
      <PaneHeader title="Name this group" onBack={() => setStep("members")} />
      <div className="min-h-0 flex-1 overflow-y-auto px-4">
        <div className="flex justify-center pt-2 pb-5">
          <button
            type="button"
            aria-label="Choose group photo"
            onClick={() => fileInput.current?.click()}
            className="relative rounded-full outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            {preview ? (
              <Avatar name={name} color="A100" imageUrl={preview} size={88} />
            ) : (
              <span className="flex h-[88px] w-[88px] items-center justify-center rounded-full bg-[var(--avatar-A100-bg)] text-[var(--avatar-A100-fg)]">
                <Users size={44} strokeWidth={1.75} aria-hidden />
              </span>
            )}
            <span className="absolute right-0 bottom-0 flex h-7 w-7 items-center justify-center rounded-full border border-border-card bg-card text-text-primary">
              <Camera size={15} aria-hidden />
            </span>
          </button>
          <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={pickPhoto} />
        </div>
        <input
          autoFocus
          value={name}
          maxLength={MAX_NAME}
          onChange={(event) => setName(event.target.value)}
          placeholder="Group name (required)"
          aria-label="Group name"
          className={inputClassName}
        />
        <div className="mt-5 flex items-center gap-3">
          <span className="text-sm text-text-primary">Disappearing messages</span>
          <button
            type="button"
            onClick={() => showToast(COMING_SOON)}
            className="flex items-center gap-1 rounded-full bg-search px-3 py-1 text-sm text-text-primary"
          >
            Off <ChevronDown size={14} aria-hidden />
          </button>
        </div>
        <h2 className="mt-6 mb-1 text-sm font-semibold text-text-primary">Members</h2>
        <ul>
          {members.map((member) => (
            <li key={member.id} className="flex items-center gap-3 py-1.5">
              <Avatar name={member.name} color={member.avatar_color} imageUrl={member.avatar_url} size={32} />
              <span className="truncate text-sm text-text-primary">{member.name}</span>
            </li>
          ))}
        </ul>
      </div>
      <AccentButton label={creating ? "Creating…" : "Create"} disabled={!name.trim() || creating} onClick={() => void create()} />
    </>
  );
}
