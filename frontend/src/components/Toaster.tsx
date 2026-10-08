"use client";

import Link from "next/link";

import { useToasts } from "@/store/toasts";

/** Signal-style toasts: small inverted pills at the bottom of the window. */
export function Toaster() {
  const toasts = useToasts((state) => state.toasts);
  const dismiss = useToasts((state) => state.dismiss);
  return (
    <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex flex-col items-center gap-2">
      {toasts.map((toast) =>
        toast.href ? (
          <Link
            key={toast.id}
            href={toast.href}
            onClick={() => dismiss(toast.id)}
            className="pointer-events-auto max-w-[min(90vw,420px)] truncate rounded-full bg-text-primary px-4 py-2 text-sm text-chat shadow-lg"
          >
            {toast.text}
          </Link>
        ) : (
          <button
            key={toast.id}
            type="button"
            onClick={() => dismiss(toast.id)}
            className="pointer-events-auto rounded-full bg-text-primary px-4 py-2 text-sm text-chat shadow-lg"
          >
            {toast.text}
          </button>
        ),
      )}
    </div>
  );
}
