export type Theme = "system" | "light" | "dark";

/** Mirrors backend `SettingsOut`. */
export type Settings = {
  theme: Theme;
  read_receipts_enabled: boolean;
  typing_indicators_enabled: boolean;
  notifications_enabled: boolean;
  enter_key_sends: boolean;
};
