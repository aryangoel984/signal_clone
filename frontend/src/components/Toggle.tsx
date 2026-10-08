type ToggleProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string; // accessible name
  disabled?: boolean;
};

/** Signal's switch: accent track when on, sampled knob colors. */
export function Toggle({ checked, onChange, label, disabled = false }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-[18px] w-[30px] shrink-0 items-center rounded-full border transition-colors disabled:opacity-50 ${
        checked ? "border-toggle-on bg-toggle-on" : "border-border-card bg-toggle-off"
      }`}
    >
      <span
        className={`inline-block h-[14px] w-[14px] rounded-full bg-toggle-knob shadow transition-transform ${
          checked ? "translate-x-[13px]" : "translate-x-[1px]"
        }`}
      />
    </button>
  );
}
