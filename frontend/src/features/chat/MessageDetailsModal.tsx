"use client";

import { useEffect, useState } from "react";

import { Avatar } from "@/components/Avatar";
import { Modal } from "@/components/Modal";
import { ApiError, apiRequest } from "@/lib/api";
import type { MessageDetails } from "@/types/message";

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

type Row = MessageDetails["recipients"][number];

/** "Message details" for my own message: who has read it, who has it, who hasn't yet. */
export function MessageDetailsModal({ messageId, onClose }: { messageId: number; onClose: () => void }) {
  const [details, setDetails] = useState<MessageDetails | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiRequest<MessageDetails>(`/messages/${messageId}/receipts`)
      .then(setDetails)
      .catch((caught: unknown) => setError(caught instanceof ApiError ? caught.detail : "Couldn't load details"));
  }, [messageId]);

  const sections: { title: string; rows: Row[]; time: (row: Row) => string | null }[] = details
    ? [
        { title: "Read by", rows: details.recipients.filter((r) => r.read_at), time: (r) => r.read_at },
        { title: "Delivered to", rows: details.recipients.filter((r) => r.delivered_at && !r.read_at), time: (r) => r.delivered_at },
        { title: "Sent to", rows: details.recipients.filter((r) => !r.delivered_at), time: () => null },
      ]
    : [];

  return (
    <Modal title="Message details" onClose={onClose} width={400}>
      {error && <p className="text-sm text-danger">{error}</p>}
      {details && (
        <>
          <p className="text-sm text-text-secondary">Sent {when(details.sent_at)}</p>
          {details.recipients.length === 0 && <p className="mt-3 text-sm text-text-secondary">No one else is in this chat.</p>}
          {sections
            .filter((section) => section.rows.length > 0)
            .map((section) => (
              <section key={section.title} className="mt-4">
                <h3 className="mb-1 text-xs font-semibold tracking-wide text-text-muted uppercase">{section.title}</h3>
                <ul>
                  {section.rows.map((row) => {
                    const time = section.time(row);
                    return (
                      <li key={row.user_id} className="flex items-center gap-3 py-1.5">
                        <Avatar name={row.name} color={row.avatar_color} imageUrl={row.avatar_url} size={28} />
                        <span className="min-w-0 flex-1 truncate text-sm text-text-primary">{row.name}</span>
                        {time && <span className="text-xs text-text-secondary">{when(time)}</span>}
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}
        </>
      )}
    </Modal>
  );
}
