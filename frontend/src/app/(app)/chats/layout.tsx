import { LeftPane } from "@/features/conversations/LeftPane";

export default function ChatsLayout({ children }: LayoutProps<"/chats">) {
  return (
    <>
      <LeftPane />
      <main className="flex min-w-0 flex-1">{children}</main>
    </>
  );
}
