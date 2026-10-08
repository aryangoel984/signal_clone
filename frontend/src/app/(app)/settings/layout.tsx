"use client";

import { useSelectedLayoutSegment } from "next/navigation";

import { SettingsNav } from "@/features/settings/SettingsNav";

/** Like Chats: below 900px, /settings shows the menu and /settings/[section] the page. */
export default function SettingsLayout({ children }: LayoutProps<"/settings">) {
  const sectionOpen = useSelectedLayoutSegment() !== null;
  return (
    <>
      <div className={`${sectionOpen ? "hidden" : "flex"} min-w-0 flex-1 pane:flex pane:flex-none`}>
        <SettingsNav />
      </div>
      <main className={`${sectionOpen ? "flex" : "hidden"} min-w-0 flex-1 pane:flex`}>{children}</main>
    </>
  );
}
