"use client";

import { X } from "lucide-react";
import { type ReactNode, useEffect, useRef } from "react";

import { Button } from "@/components/Button";
import { IconButton } from "@/components/IconButton";

type ModalProps = {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  width?: number;
};

/** Centered dialog. Escape or clicking the backdrop closes it; focus moves inside and Tab stays inside. */
export function Modal({ title, onClose, children, footer, width = 420 }: ModalProps) {
  const dialog = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const focusable = () =>
      [...(dialog.current?.querySelectorAll<HTMLElement>("button, input, select, textarea, [tabindex]") ?? [])].filter(
        (element) => !element.hasAttribute("disabled"),
      );
    (focusable()[1] ?? focusable()[0])?.focus(); // first control after the close button
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab") return;
      const items = focusable();
      const first = items[0];
      const last = items.at(-1);
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      previous?.focus();
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="flex max-h-[85vh] w-full flex-col rounded-card border border-border-card bg-card shadow-xl"
        style={{ maxWidth: width }}
      >
        <header className="flex items-center gap-2 px-4 pt-3 pb-2">
          <h2 className="flex-1 text-base font-semibold text-text-primary">{title}</h2>
          <IconButton icon={X} label="Close" onClick={onClose} />
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-3">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-border px-4 py-3">{footer}</footer>}
      </div>
    </div>
  );
}

type ConfirmDialogProps = {
  title: string;
  message: string;
  confirmLabel: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({ title, message, confirmLabel, danger = false, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <Modal
      title={title}
      onClose={onCancel}
      width={360}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={onConfirm} className={danger ? "!bg-danger !text-on-primary" : ""}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-sm text-text-secondary">{message}</p>
    </Modal>
  );
}
