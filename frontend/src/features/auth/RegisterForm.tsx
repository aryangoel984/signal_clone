"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/Button";
import { ApiError, apiRequest } from "@/lib/api";
import { COUNTRIES, toE164 } from "@/lib/phone";
import { savePendingPhone } from "@/lib/session-storage";

import { AuthScreen, FieldError, inputClassName } from "./AuthScreen";

const DEMO_ACCOUNTS = [
  { name: "Alex Rivera", countryCode: "US", national: "555 010 0001" },
  { name: "Priya Sharma", countryCode: "US", national: "555 010 0002" },
] as const;

export function RegisterForm() {
  const router = useRouter();
  const [countryCode, setCountryCode] = useState("US");
  const [national, setNational] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const dial = COUNTRIES.find((country) => country.code === countryCode)?.dial ?? "1";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const phone = toE164(dial, national);
    if (!phone) {
      setError("Enter a valid phone number.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest("/auth/otp/request", { method: "POST", body: { phone_number: phone } });
      savePendingPhone(phone);
      router.push("/verify");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Something went wrong.");
      setSubmitting(false);
    }
  }

  return (
    <AuthScreen title="Phone number" subtitle="Enter your phone number to get started.">
      <form onSubmit={handleSubmit} noValidate>
        <label htmlFor="country" className="text-xs font-medium text-text-secondary">
          Country
        </label>
        <select
          id="country"
          value={countryCode}
          onChange={(event) => setCountryCode(event.target.value)}
          className={`${inputClassName} mt-1`}
        >
          {COUNTRIES.map((country) => (
            <option key={country.code} value={country.code}>
              {country.name} (+{country.dial})
            </option>
          ))}
        </select>

        <label htmlFor="phone" className="mt-4 block text-xs font-medium text-text-secondary">
          Phone number
        </label>
        <div className="mt-1 flex gap-2">
          <span className="flex items-center rounded-control bg-search px-3 text-sm text-text-secondary">+{dial}</span>
          <input
            id="phone"
            type="tel"
            inputMode="tel"
            autoComplete="tel-national"
            autoFocus
            placeholder="Phone number"
            value={national}
            onChange={(event) => setNational(event.target.value)}
            className={inputClassName}
          />
        </div>
        <FieldError message={error} />

        <Button type="submit" disabled={submitting || national.trim() === ""} className="mt-6 w-full">
          {submitting ? "Sending…" : "Continue"}
        </Button>
      </form>

      <section aria-labelledby="demo-accounts" className="mt-8 rounded-card border border-border-card bg-card p-4">
        <h2 id="demo-accounts" className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          Demo accounts
        </h2>
        <p className="mt-1 text-xs text-text-secondary">
          Fills in a seeded account. The verification code is always 123456.
        </p>
        <div className="mt-3 flex flex-col gap-2">
          {DEMO_ACCOUNTS.map((account) => (
            <Button
              key={account.name}
              variant="secondary"
              className="flex justify-between"
              onClick={() => {
                setCountryCode(account.countryCode);
                setNational(account.national);
                setError(null);
              }}
            >
              <span>{account.name}</span>
              <span className="text-text-secondary">+1 {account.national}</span>
            </Button>
          ))}
        </div>
      </section>
    </AuthScreen>
  );
}
