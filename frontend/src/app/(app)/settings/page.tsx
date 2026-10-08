"use client";

import { SETTINGS_SECTIONS } from "@/features/settings/sections";

const General = SETTINGS_SECTIONS.general as () => React.JSX.Element;

export default function SettingsIndexPage() {
  return <General />;
}
