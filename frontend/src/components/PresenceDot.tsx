/** Green "online" dot, placed over the bottom-right of an avatar. */
export function PresenceDot({ size = 12 }: { size?: number }) {
  return (
    <span
      aria-label="Online"
      className="absolute right-0 bottom-0 rounded-full border-2 border-sidebar bg-presence-online"
      style={{ width: size, height: size }}
    />
  );
}
