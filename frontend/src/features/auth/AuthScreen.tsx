import type { ReactNode } from "react";

import { SignalLogo } from "@/components/SignalLogo";

type AuthScreenProps = {
  title: string;
  subtitle: ReactNode;
  children: ReactNode;
};

/** Centered layout shared by the register / verify / onboarding steps. */
export function AuthScreen({ title, subtitle, children }: AuthScreenProps) {
  return (
    <main className="flex flex-1 items-center justify-center bg-chat px-4 py-10">
      <div className="flex w-full max-w-sm flex-col items-center text-center">
        <SignalLogo size={56} />
        <h1 className="mt-6 text-2xl font-semibold text-text-primary">{title}</h1>
        <p className="mt-2 text-sm text-text-secondary">{subtitle}</p>
        <div className="mt-8 w-full text-left">{children}</div>
      </div>
    </main>
  );
}

export const inputClassName =
  "w-full rounded-control bg-search px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none focus:ring-2 focus:ring-primary";

export function FieldError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="mt-2 text-sm text-danger">
      {message}
    </p>
  );
}
