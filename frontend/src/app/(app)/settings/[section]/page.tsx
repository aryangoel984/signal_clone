"use client";

import { useParams } from "next/navigation";

import { SETTINGS_SECTIONS } from "@/features/settings/sections";

export default function SettingsSectionPage() {
  const { section } = useParams<{ section: string }>();
  const Section = SETTINGS_SECTIONS[section];
  if (!Section) {
    return <div className="flex flex-1 items-center justify-center bg-chat text-sm text-text-secondary">Unknown settings page.</div>;
  }
  return <Section />;
}
