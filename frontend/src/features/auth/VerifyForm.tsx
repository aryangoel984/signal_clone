"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState, useSyncExternalStore } from "react";

import { Button } from "@/components/Button";
import { ApiError, apiRequest } from "@/lib/api";
import { loadPendingPhone, savePendingPhone } from "@/lib/session-storage";
import { useAuthStore } from "@/store/auth";
import type { AuthResponse } from "@/types/user";

import { AuthScreen, FieldError, inputClassName } from "./AuthScreen";
import { AuthSplash } from "./AuthSplash";

const CODE_LENGTH = 6;

// sessionStorage has no change events within a tab; the value is only read on render.
const subscribeNever = () => () => {};

export function VerifyForm() {
  const router = useRouter();
  const signIn = useAuthStore((state) => state.signIn);
  // undefined on the server and during hydration, then the stored number (or null).
  const phone = useSyncExternalStore(subscribeNever, loadPendingPhone, () => undefined);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (phone === null) router.replace("/register"); // opened directly or in a new tab: nothing to verify
  }, [phone, router]);

  async function verify(fullCode: string) {
    if (!phone || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await apiRequest<AuthResponse>("/auth/otp/verify", {
        method: "POST",
        body: { phone_number: phone, code: fullCode },
      });
      savePendingPhone(null);
      signIn(result.token, result.user); // the guard then routes to /onboarding or /chats
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Something went wrong.");
      setCode("");
      setSubmitting(false);
    }
  }

  function handleChange(value: string) {
    const digits = value.replace(/\D/g, "").slice(0, CODE_LENGTH);
    setCode(digits);
    if (digits.length === CODE_LENGTH) void verify(digits);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (code.length === CODE_LENGTH) void verify(code);
  }

  if (!phone) return <AuthSplash />;

  return (
    <AuthScreen title="Verification code" subtitle={<>Enter the code we sent to {phone}</>}>
      <form onSubmit={handleSubmit} noValidate>
        <label htmlFor="code" className="sr-only">
          Verification code
        </label>
        <input
          id="code"
          inputMode="numeric"
          autoComplete="one-time-code"
          autoFocus
          maxLength={CODE_LENGTH}
          placeholder="••••••"
          value={code}
          disabled={submitting}
          onChange={(event) => handleChange(event.target.value)}
          className={`${inputClassName} text-center text-2xl tracking-[0.6em]`}
        />
        <FieldError message={error} />
        <p className="mt-3 text-center text-xs text-text-muted">Demo: the code is always 123456.</p>

        <Button type="submit" disabled={submitting || code.length !== CODE_LENGTH} className="mt-6 w-full">
          {submitting ? "Verifying…" : "Continue"}
        </Button>
        <div className="mt-4 text-center">
          <Button variant="link" onClick={() => router.replace("/register")}>
            Wrong number?
          </Button>
        </div>
      </form>
    </AuthScreen>
  );
}
