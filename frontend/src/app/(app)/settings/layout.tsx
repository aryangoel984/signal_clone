import { SettingsNav } from "@/features/settings/SettingsNav";

export default function SettingsLayout({ children }: LayoutProps<"/settings">) {
  return (
    <>
      <SettingsNav />
      <main className="flex min-w-0 flex-1">{children}</main>
    </>
  );
}
