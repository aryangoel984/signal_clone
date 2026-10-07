import hashlib

# Signal's avatar color names. The actual light/dark colors live in the frontend theme.
AVATAR_COLORS = ("A100", "A110", "A120", "A130", "A140", "A150", "A160", "A170", "A180", "A190", "A200", "A210")


def avatar_color_for(key: str) -> str:
    """Deterministic color for a stable key (a phone number, or "group:<name>")."""
    digest = hashlib.sha256(key.encode()).digest()
    return AVATAR_COLORS[digest[0] % len(AVATAR_COLORS)]
