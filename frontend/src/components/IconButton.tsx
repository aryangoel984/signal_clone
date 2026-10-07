import type { LucideIcon } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";

type IconButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  icon: LucideIcon;
  label: string; // accessible name; icon-only buttons need one
  active?: boolean;
  size?: number;
};

export function IconButton({ icon: Icon, label, active = false, size = 20, className = "", type = "button", ...props }: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      aria-pressed={active || undefined}
      className={`inline-flex items-center justify-center rounded-control p-1.5 text-text-primary transition-colors hover:bg-selected ${active ? "bg-selected" : ""} ${className}`}
      {...props}
    >
      <Icon size={size} strokeWidth={1.75} aria-hidden />
    </button>
  );
}
