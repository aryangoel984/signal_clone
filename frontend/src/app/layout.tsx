import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { AuthBootstrap } from "@/features/auth/AuthBootstrap";

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
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <AuthBootstrap />
        {children}
      </body>
    </html>
  );
}
