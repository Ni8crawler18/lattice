export { auth as middleware } from "@/auth";

// Gate everything except the public front door: landing, /get-access, the
// deck, auth routes and static assets. Anything else redirects to sign-in.
export const config = {
  matcher: [
    "/((?!api/auth|slides\\.html|_next/static|_next/image|favicon|.*\\.(?:png|svg|jpg|jpeg|ico|webp|txt|csv)$|$).*)",
  ],
};
