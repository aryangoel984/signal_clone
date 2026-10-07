const TOKENS = ["A100", "A110", "A120", "A130", "A140", "A150", "A160", "A170", "A180", "A190", "A200", "A210"];

/** Signal colors group sender names independently of the avatar color; derive one from the user id. */
export function nameColor(userId: number): string {
  const hashed = Math.imul(userId ^ 0x5bd1e995, 0x27d4eb2d) >>> 0;
  return `var(--name-${TOKENS[hashed % TOKENS.length]})`;
}
