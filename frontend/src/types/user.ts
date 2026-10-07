/** Mirrors backend `MeResponse`. */
export type Me = {
  id: number;
  phone_number: string;
  username: string | null;
  display_name: string | null;
  about: string | null;
  avatar_url: string | null;
  avatar_color: string;
  created_at: string;
};

/** Mirrors backend `AuthResponse`. */
export type AuthResponse = {
  token: string;
  user: Me;
  is_new_user: boolean;
};
