import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { AuthBootstrap } from "@/features/auth/AuthBootstrap";
import { THEME_BOOT_SCRIPT } from "@/lib/theme";

import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Signal",
  description: "A Signal Desktop clone",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning: the inline script sets data-theme before React hydrates.
    <html lang="en" className={`${inter.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body className="flex min-h-full flex-col font-sans">
        <AuthBootstrap />
        {children}
      </body>
    </html>
  );
}
