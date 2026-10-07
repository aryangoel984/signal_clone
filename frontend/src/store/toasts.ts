import { create } from "zustand";

export type Toast = { id: number; text: string };

type ToastState = {
  toasts: Toast[];
  show: (text: string) => void;
  dismiss: (id: number) => void;
};

const VISIBLE_MS = 3500;
let nextId = 1;

export const useToasts = create<ToastState>()((set, get) => ({
  toasts: [],
  show: (text) => {
    const id = nextId++;
    set({ toasts: [...get().toasts, { id, text }] });
    setTimeout(() => get().dismiss(id), VISIBLE_MS);
  },
  dismiss: (id) => set({ toasts: get().toasts.filter((toast) => toast.id !== id) }),
}));

export const showToast = (text: string) => useToasts.getState().show(text);
export const COMING_SOON = "Coming soon";
