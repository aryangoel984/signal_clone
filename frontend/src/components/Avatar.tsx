import { mediaUrl } from "@/lib/api";

type AvatarProps = {
  name: string | null;
  color: string; // avatar color token, e.g. "A110"
  imageUrl?: string | null; // backend media path or a local object URL
  size?: number;
};

const KNOWN_COLORS = new Set(["A100", "A110", "A120", "A130", "A140", "A150", "A160", "A170", "A180", "A190", "A200", "A210"]);

export function initials(name: string | null): string {
  const words = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "";
  const first = words[0]?.[0] ?? "";
  const last = words.length > 1 ? (words[words.length - 1]?.[0] ?? "") : "";
  return (first + last).toUpperCase();
}

export function Avatar({ name, color, imageUrl, size = 48 }: AvatarProps) {
  const token = KNOWN_COLORS.has(color) ? color : "A210";
  const src = imageUrl?.startsWith("/media/") ? mediaUrl(imageUrl) : imageUrl;

  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- avatars come from the API host, not next/image
      <img src={src} alt="" width={size} height={size} className="shrink-0 rounded-full object-cover" style={{ width: size, height: size }} />
    );
  }
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 select-none items-center justify-center rounded-full font-medium"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.42,
        background: `var(--avatar-${token}-bg)`,
        color: `var(--avatar-${token}-fg)`,
      }}
    >
      {initials(name)}
    </span>
  );
}
