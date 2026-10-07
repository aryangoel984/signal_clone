export type Country = { code: string; name: string; dial: string };

export const COUNTRIES: readonly Country[] = [
  { code: "US", name: "United States", dial: "1" },
  { code: "IN", name: "India", dial: "91" },
  { code: "GB", name: "United Kingdom", dial: "44" },
  { code: "CA", name: "Canada", dial: "1" },
  { code: "DE", name: "Germany", dial: "49" },
  { code: "FR", name: "France", dial: "33" },
  { code: "AU", name: "Australia", dial: "61" },
  { code: "JP", name: "Japan", dial: "81" },
  { code: "BR", name: "Brazil", dial: "55" },
  { code: "SG", name: "Singapore", dial: "65" },
  { code: "AE", name: "United Arab Emirates", dial: "971" },
];

// Same rule as the backend (schemas/common.py).
const E164 = /^\+[1-9]\d{7,14}$/;

/**
 * Builds an E.164 number from a dial code and what the user typed.
 * Drops spaces/dashes/brackets and the national trunk "0" ("096548 30484" in India
 * becomes +919654830484). A pasted full "+..." number is used as is.
 * Returns null if the result isn't valid E.164.
 */
export function toE164(dial: string, input: string): string | null {
  const trimmed = input.trim();
  const candidate = trimmed.startsWith("+")
    ? `+${trimmed.slice(1).replace(/\D/g, "")}`
    : `+${dial}${trimmed.replace(/\D/g, "").replace(/^0+/, "")}`;
  return E164.test(candidate) ? candidate : null;
}
