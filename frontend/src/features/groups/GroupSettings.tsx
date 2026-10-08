"use client";

import { Camera, ChevronLeft, Ellipsis, LogOut, Pencil, ShieldCheck, ShieldOff, UserMinus, UserPlus } from "lucide-react";
import { type ChangeEvent, useRef, useState } from "react";

import { Avatar } from "@/components/Avatar";
import { Button } from "@/components/Button";
import { IconButton } from "@/components/IconButton";
import { belowElement, Menu, type MenuItem, type MenuPosition } from "@/components/Menu";
import { ConfirmDialog, Modal } from "@/components/Modal";
import { inputClassName } from "@/features/auth/AuthScreen";
import { ApiError, apiRequest } from "@/lib/api";
import { downscaleAvatar } from "@/lib/image";
import { showToast } from "@/store/toasts";
import type { UserPublic } from "@/types/contact";
import type { ConversationDetail, Member } from "@/types/conversation";

import { MemberPicker } from "./MemberPicker";

type GroupSettingsProps = {
  conversation: ConversationDetail;
  myId: number;
  onBack: () => void;
  onChanged: (conversation: ConversationDetail) => void;
};

type Confirm = { title: string; message: string; label: string; action: () => Promise<void> };

/** Signal's "Group settings" in the main pane: photo, name, members (admin controls), leave. */
export function GroupSettings({ conversation, myId, onBack, onChanged }: GroupSettingsProps) {
  const isAdmin = conversation.my_role === "admin" && conversation.can_send;
  const [editingName, setEditingName] = useState(false);
  const [name, setName] = useState(conversation.title);
  const [adding, setAdding] = useState(false);
  const [toAdd, setToAdd] = useState<UserPublic[]>([]);
  const [menu, setMenu] = useState<{ member: Member; position: MenuPosition } | null>(null);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const base = `/groups/${conversation.id}`;

  async function run(action: () => Promise<ConversationDetail | void>, done?: string) {
    try {
      const updated = await action();
      onChanged(updated ?? (await apiRequest<ConversationDetail>(`/conversations/${conversation.id}`)));
      if (done) showToast(done);
    } catch (error) {
      showToast(error instanceof ApiError ? error.detail : "Something went wrong");
    }
  }

  async function changePhoto(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", await downscaleAvatar(file), "group.jpg");
    await run(() => apiRequest<ConversationDetail>(`${base}/avatar`, { method: "PUT", body: form }), "Photo updated");
  }

  const members = [...conversation.members].sort(
    (a, b) =>
      Number(b.user_id === myId) - Number(a.user_id === myId) ||
      Number(b.role === "admin") - Number(a.role === "admin") ||
      a.name.localeCompare(b.name),
  );

  function memberMenu(member: Member): MenuItem[] {
    const role: MenuItem =
      member.role === "admin"
        ? {
            label: "Remove as admin",
            icon: ShieldOff,
            onSelect: () => void run(() => apiRequest(`${base}/members/${member.user_id}`, { method: "PATCH", body: { role: "member" } })),
          }
        : {
            label: "Make admin",
            icon: ShieldCheck,
            onSelect: () => void run(() => apiRequest(`${base}/members/${member.user_id}`, { method: "PATCH", body: { role: "admin" } })),
          };
    return [
      role,
      {
        label: "Remove from group",
        icon: UserMinus,
        danger: true,
        onSelect: () =>
          setConfirm({
            title: `Remove ${member.name}?`,
            message: `${member.name} will be removed from "${conversation.title}". They'll keep the messages they already have.`,
            label: "Remove",
            action: () => run(() => apiRequest<void>(`${base}/members/${member.user_id}`, { method: "DELETE" }), "Member removed"),
          }),
      },
    ];
  }

  return (
    <div className="flex min-w-0 flex-1 flex-col bg-chat">
      <header className="relative z-10 flex h-[52px] shrink-0 items-center gap-2 px-3 shadow-[0_2px_10px_var(--header-shadow)]">
        <IconButton icon={ChevronLeft} label="Back to chat" onClick={onBack} />
        <h1 className="text-sm font-semibold text-text-primary">Group settings</h1>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-xl flex-col items-center px-6 pt-8 pb-10">
          <div className="relative">
            <Avatar name={conversation.title} color={conversation.avatar_color} imageUrl={conversation.avatar_url} size={80} isGroup />
            {isAdmin && (
              <>
                <button
                  type="button"
                  aria-label="Change group photo"
                  onClick={() => fileInput.current?.click()}
                  className="absolute right-0 bottom-0 flex h-7 w-7 items-center justify-center rounded-full border border-border-card bg-card text-text-primary"
                >
                  <Camera size={14} aria-hidden />
                </button>
                <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={changePhoto} />
              </>
            )}
          </div>

          {editingName ? (
            <form
              className="mt-4 flex w-full max-w-sm gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                void run(() => apiRequest<ConversationDetail>(base, { method: "PATCH", body: { name } })).then(() => setEditingName(false));
              }}
            >
              <input autoFocus value={name} maxLength={32} onChange={(e) => setName(e.target.value)} aria-label="Group name" className={inputClassName} />
              <Button type="submit" disabled={!name.trim()}>
                Save
              </Button>
            </form>
          ) : (
            <h2 className="mt-4 flex items-center gap-1 text-xl font-semibold text-text-primary">
              {conversation.title}
              {isAdmin && (
                <IconButton
                  icon={Pencil}
                  size={16}
                  label="Edit group name"
                  onClick={() => {
                    setName(conversation.title);
                    setEditingName(true);
                  }}
                />
              )}
            </h2>
          )}
          {!conversation.can_send && <p className="mt-2 text-sm text-text-secondary">You&apos;re no longer a member of this group.</p>}

          <section className="mt-8 w-full">
            <h3 className="mb-2 text-sm font-semibold text-text-primary">
              {conversation.member_count} {conversation.member_count === 1 ? "member" : "members"}
            </h3>
            <ul className="rounded-card border border-border-card bg-card py-1">
              {isAdmin && (
                <li>
                  <button type="button" onClick={() => setAdding(true)} className="flex w-full items-center gap-3 px-4 py-2 text-left text-sm text-text-primary hover:bg-selected">
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-search">
                      <UserPlus size={16} aria-hidden />
                    </span>
                    Add members
                  </button>
                </li>
              )}
              {members.map((member) => (
                <li key={member.user_id} className="flex items-center gap-3 px-4 py-2">
                  <Avatar name={member.name} color={member.avatar_color} imageUrl={member.avatar_url} size={32} />
                  <span className="min-w-0 flex-1 truncate text-sm text-text-primary">{member.name}</span>
                  {member.role === "admin" && <span className="text-xs text-text-secondary">Admin</span>}
                  {isAdmin && member.user_id !== myId && (
                    <IconButton
                      icon={Ellipsis}
                      size={18}
                      label={`Options for ${member.name}`}
                      onClick={(event) => setMenu({ member, position: belowElement(event.currentTarget) })}
                    />
                  )}
                </li>
              ))}
            </ul>
          </section>

          {conversation.can_send && (
            <button
              type="button"
              onClick={() =>
                setConfirm({
                  title: "Leave group?",
                  message: "You'll no longer be able to send or receive messages in this group.",
                  label: "Leave",
                  action: () => run(() => apiRequest<void>(`${base}/members/${myId}`, { method: "DELETE" }), "You left the group"),
                })
              }
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-card border border-border-card bg-card py-2.5 text-sm font-medium text-danger hover:bg-selected"
            >
              <LogOut size={16} aria-hidden /> Leave group
            </button>
          )}
        </div>
      </div>

      {menu && (
        <Menu items={memberMenu(menu.member)} position={{ ...menu.position, left: menu.position.left - 200 }} onClose={() => setMenu(null)} />
      )}
      {confirm && (
        <ConfirmDialog
          title={confirm.title}
          message={confirm.message}
          confirmLabel={confirm.label}
          danger
          onCancel={() => setConfirm(null)}
          onConfirm={() => {
            const { action } = confirm;
            setConfirm(null);
            void action();
          }}
        />
      )}
      {adding && (
        <Modal
          title="Add members"
          width={440}
          onClose={() => {
            setAdding(false);
            setToAdd([]);
          }}
          footer={
            <Button
              disabled={toAdd.length === 0}
              onClick={() => {
                const ids = toAdd.map((person) => person.id);
                setAdding(false);
                setToAdd([]);
                void run(() => apiRequest<ConversationDetail>(`${base}/members`, { method: "POST", body: { user_ids: ids } }), "Members added");
              }}
            >
              Add {toAdd.length > 0 ? toAdd.length : ""}
            </Button>
          }
        >
          <div className="-mx-4 flex h-[50vh] flex-col">
            <MemberPicker selected={toAdd} onChange={setToAdd} excludeIds={conversation.members.map((m) => m.user_id)} />
          </div>
        </Modal>
      )}
    </div>
  );
}
