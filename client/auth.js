import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

// Google sign-in exists to remove typing, not to gate anything: it pre-fills
// name and email so claiming a key is one click. The manual email form stays,
// because a developer evaluating an API should never be forced to hand over a
// Google account first.
export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    }),
  ],
  trustHost: true,
  // Short-lived sessions: this console is handed out at a demo, often on a
  // shared screen. 10 minutes of inactivity signs you out; any request inside
  // that window slides the expiry forward, so active use is never interrupted.
  session: { strategy: "jwt", maxAge: 10 * 60, updateAge: 60 },
  // An unauthenticated click on "Open console" lands on the page that issues
  // a key, so evaluating the product and claiming access are the same step.
  pages: { signIn: "/" },
  callbacks: {
    authorized: ({ auth }) => !!auth?.user,
  },
  events: {
    // A Google sign-in used to be invisible to the traction ledger: only the
    // manual email form ever called /signup, so someone who clicked "Continue
    // with Google" was a real user we never counted. This records them on the
    // way in. /signup is idempotent on email, so repeat logins do not inflate
    // the number, and a failure here must never block sign-in.
    async signIn({ user }) {
      if (!user?.email) return;
      const api = (process.env.NEXT_PUBLIC_LATTICE_API || "https://lattice-api-fs5f.onrender.com").replace(/\/$/, "");
      // HARD timeout, because this runs inside the OAuth callback. The API is
      // on Render's free plan and spins down after ~15 minutes idle; a cold
      // start takes 30-60s. An unbounded await here outlived the serverless
      // function, killed the callback route, and surfaced to the user as
      // "Server error - there is a problem with the server configuration".
      // Signing in must never depend on the API being awake.
      const ctl = new AbortController();
      const timer = setTimeout(() => ctl.abort(), 2500);
      try {
        await fetch(`${api}/signup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: user.email, name: user.name || "" }),
          signal: ctl.signal,
        });
      } catch {
        /* Cold API or slow network: we lose this one ledger row, not the
           login. The row is recovered on any later sign-in, since /signup is
           idempotent on email. */
      } finally {
        clearTimeout(timer);
      }
    },
  },
});
