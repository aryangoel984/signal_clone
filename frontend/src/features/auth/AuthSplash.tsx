import { SignalLogo } from "@/components/SignalLogo";

/** Neutral screen shown while the session is unknown or a redirect is pending.
 *  It's never the login screen and never the app, so a reload can't flash the wrong one. */
export function AuthSplash() {
  return (
    <div className="flex flex-1 items-center justify-center bg-sidebar" aria-busy="true" aria-label="Loading">
      <SignalLogo size={72} />
    </div>
  );
}
