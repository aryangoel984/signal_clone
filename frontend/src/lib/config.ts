// Each variable is read with a literal `process.env.NEXT_PUBLIC_*` expression so
// Next.js can inline it at build time. Dynamic lookups (process.env[name]) are
// not inlined and would be undefined in the browser.
const apiUrl = process.env.NEXT_PUBLIC_API_URL;
const wsUrl = process.env.NEXT_PUBLIC_WS_URL;

function required(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(`Missing ${name}. Copy frontend/.env.example to frontend/.env.local and set it.`);
  }
  return value.replace(/\/+$/, "");
}

export const config = {
  apiUrl: required("NEXT_PUBLIC_API_URL", apiUrl),
  wsUrl: required("NEXT_PUBLIC_WS_URL", wsUrl),
} as const;
