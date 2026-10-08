/** Signal's typing animation: three dots pulsing in turn. */
export function TypingDots({ size = 7 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-1" role="img" aria-label="Typing">
      {[0, 1, 2].map((dot) => (
        <span key={dot} className="typing-dot rounded-full bg-current" style={{ width: size, height: size }} />
      ))}
    </span>
  );
}
