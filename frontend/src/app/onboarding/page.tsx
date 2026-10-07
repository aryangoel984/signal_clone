"use client";

import { RequireSignedInWithoutProfile } from "@/features/auth/guards";
import { OnboardingForm } from "@/features/auth/OnboardingForm";

export default function OnboardingPage() {
  return (
    <RequireSignedInWithoutProfile>
      <OnboardingForm />
    </RequireSignedInWithoutProfile>
  );
}
