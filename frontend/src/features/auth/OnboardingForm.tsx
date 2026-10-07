"use client";

import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";

import { Avatar } from "@/components/Avatar";
import { Button } from "@/components/Button";
import { ApiError, apiRequest } from "@/lib/api";
import { downscaleAvatar } from "@/lib/image";
import { useAuthStore } from "@/store/auth";
import type { Me } from "@/types/user";

import { AuthScreen, FieldError, inputClassName } from "./AuthScreen";

const ACCEPTED_TYPES = "image/jpeg,image/png,image/webp";

export function OnboardingForm() {
  const user = useAuthStore((state) => state.user);
  const setUser = useAuthStore((state) => state.setUser);
  const fileInput = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [about, setAbout] = useState("");
  const [avatar, setAvatar] = useState<Blob | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const scaled = await downscaleAvatar(file);
      setAvatar(scaled);
      setPreviewUrl(URL.createObjectURL(scaled));
      setError(null);
    } catch {
      setError("That image couldn't be read. Try a JPEG, PNG or WebP file.");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      let updated = await apiRequest<Me>("/users/me", {
        method: "PATCH",
        body: { display_name: name, ...(about.trim() && { about }) },
      });
      if (avatar) {
        const form = new FormData();
        form.append("file", avatar, "avatar.jpg");
        updated = await apiRequest<Me>("/users/me/avatar", { method: "PUT", body: form });
      }
      setUser(updated); // the guard then routes to /chats
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Something went wrong.");
      setSubmitting(false);
    }
  }

  return (
    <AuthScreen title="Set up your profile" subtitle="Your profile is visible to people you message.">
      <form onSubmit={handleSubmit} noValidate>
        <div className="flex flex-col items-center">
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-primary"
            aria-label="Choose profile photo"
          >
            <Avatar name={name || null} color={user?.avatar_color ?? "A210"} imageUrl={previewUrl} size={88} />
          </button>
          <Button variant="link" className="mt-2" onClick={() => fileInput.current?.click()}>
            {previewUrl ? "Change photo" : "Add photo"}
          </Button>
          <input ref={fileInput} type="file" accept={ACCEPTED_TYPES} hidden onChange={handleFile} />
        </div>

        <label htmlFor="name" className="mt-6 block text-xs font-medium text-text-secondary">
          Name (required)
        </label>
        <input
          id="name"
          autoFocus
          maxLength={64}
          autoComplete="name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          className={`${inputClassName} mt-1`}
        />

        <label htmlFor="about" className="mt-4 block text-xs font-medium text-text-secondary">
          About
        </label>
        <input
          id="about"
          maxLength={140}
          placeholder="Write a few words about yourself"
          value={about}
          onChange={(event) => setAbout(event.target.value)}
          className={`${inputClassName} mt-1`}
        />
        <FieldError message={error} />

        <Button type="submit" disabled={submitting || name.trim() === ""} className="mt-6 w-full">
          {submitting ? "Saving…" : "Save"}
        </Button>
      </form>
    </AuthScreen>
  );
}
