import type { ButtonHTMLAttributes } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "link";
};

const VARIANTS = {
  primary: "rounded-full bg-primary px-6 py-2.5 text-on-primary hover:brightness-110 disabled:opacity-50",
  secondary: "rounded-full bg-button-secondary px-4 py-2 text-text-primary hover:bg-selected disabled:opacity-50",
  link: "text-primary hover:underline disabled:opacity-50",
} as const;

export function Button({ variant = "primary", className = "", type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={`text-sm font-medium transition-[filter,background-color] disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}
