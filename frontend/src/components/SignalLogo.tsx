/** Speech-bubble mark in the primary color (an original drawing, not Signal's trademark logo). */
export function SignalLogo({ size = 64 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden className="text-primary">
      <circle cx="32" cy="32" r="30" fill="none" stroke="currentColor" strokeWidth="3" strokeDasharray="5 3.2" />
      <path
        d="M32 14c-10 0-18 7.2-18 16.2 0 4.6 2.1 8.7 5.4 11.7L18 50l8.6-3.9c1.7.5 3.5.7 5.4.7 10 0 18-7.2 18-16.3S42 14 32 14Z"
        fill="currentColor"
      />
    </svg>
  );
}
