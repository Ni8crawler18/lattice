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
});
