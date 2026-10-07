"use client";

// Temporary phase-0 status page: proves the frontend can reach the backend.
// Replaced in phase 2 by a redirect to /register or /chats.

import { useEffect, useState } from "react";

import { ApiError, apiRequest } from "@/lib/api";

type HealthState = { kind: "loading" } | { kind: "ok" } | { kind: "error"; message: string };

export default function StatusPage() {
  const [health, setHealth] = useState<HealthState>({ kind: "loading" });

  useEffect(() => {
    apiRequest<{ status: "ok" }>("/health")
      .then(() => setHealth({ kind: "ok" }))
      .catch((error: unknown) => {
        const message = error instanceof ApiError ? error.detail : "Unexpected error";
        setHealth({ kind: "error", message });
      });
  }, []);

  return (
    <main className="flex flex-1 items-center justify-center bg-sidebar p-4">
      <section className="w-full max-w-sm rounded-card border border-border-card bg-card p-6">
        <h1 className="text-lg font-semibold text-text-primary">Signal clone</h1>
        <p className="mt-1 text-sm text-text-secondary">Phase 0 status check</p>

        <p className="mt-6 text-sm" role="status">
          {health.kind === "loading" && <span className="text-text-muted">Checking backend…</span>}
          {health.kind === "ok" && <span className="text-text-primary">Backend: ok</span>}
          {health.kind === "error" && <span className="text-danger">Backend: {health.message}</span>}
        </p>

        <div className="mt-6 flex gap-2">
          <span className="rounded-bubble bg-bubble-incoming px-3 py-1.5 text-sm text-on-bubble-incoming">
            Incoming
          </span>
          <span className="rounded-bubble bg-bubble-outgoing px-3 py-1.5 text-sm text-on-bubble-outgoing">
            Outgoing
          </span>
        </div>
      </section>
    </main>
  );
}
