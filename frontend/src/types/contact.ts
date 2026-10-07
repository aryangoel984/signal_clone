/** Mirrors backend `UserPublic`: another user as the viewer sees them. */
export type UserPublic = {
  id: number;
  name: string;
  display_name: string | null;
  username: string | null;
  about: string | null;
  avatar_url: string | null;
  avatar_color: string;
  phone_number: string | null; // only for my contacts
  is_contact: boolean;
  nickname: string | null;
};
