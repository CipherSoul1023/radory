# Radory authentication foundation

The approved custom React pages use the installed `@clerk/react` 6.17.6 APIs. Clerk owns passwords, verification, password resets, Google OAuth and organization membership. The existing provider and environment variables are reused. No workspace records, organizations, onboarding forms or product screens are created by these flows.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Public landing page |
| `/sign-up` | Password signup, verification and resend; Google signup |
| `/sign-in` | Password or Google sign-in; device trust / MFA challenge |
| `/forgot-password` | Email reset code, verification, new password |
| `/sso-callback` | Clerk `HandleSSOCallback` completion and account transfer |
| `/accept-invitation` | Clerk organization invitation ticket handling |
| `/auth/continue` | Fresh membership lookup and session-task check |
| `/setup-workspace` | Authenticated placeholder for users without a brokerage |
| `/app` | Authenticated workspace placeholder, API check and sign-out |

Signed-out visitors to protected routes are sent to sign-in. Signed-in visitors to signup or sign-in are sent through membership routing. Membership fetch failures never count as zero memberships. All membership pages are fetched before making a decision. One membership is activated; multiple memberships preserve a valid active organization or require an explicit selection. An accepted invitation with no visible membership stays on a retry screen instead of being sent to setup.

Invitation query parameters are passed only to Clerk's ticket APIs. Clerk validates the ticket and establishes membership; Radory never decodes it or creates a replacement invitation system. Invitation signup uses the ticket/password flow (the ticket verifies email), and Google is disabled for that specific flow to avoid losing the invitation. Normal Google signup/sign-in is supported. Sign-in, signup, password reset, SSO, MFA and device-trust continuations retain a non-secret invitation routing marker. Expired or rejected invitations display an error and never open a workspace.

Pending Clerk `choose-organization` tasks use the same membership decision. Other pending account tasks block application access. If the Clerk project requires MFA enrollment, the administrator must arrange enrollment; a custom MFA enrollment UI is outside this foundation. Additional required signup fields configured in Clerk surface a requirement message rather than silently bypassing them.

## API boundary

`GET /api/me` requires `Authorization: Bearer <Clerk session token>`. The existing RS256 verifier checks the JWKS signature, issuer, timestamps, required user/session claims, authorized frontend origin and configured audience. Pending session tokens are rejected. The response contains only verified user ID, session ID, active organization ID and role (v1 and v2 claims supported), with `Cache-Control: no-store`. Browser-supplied identity and organization query parameters are ignored. Membership-dependent product authorization will be added with future endpoints.

`useAuthenticatedApi` gets each token from Clerk's session API; it does not persist tokens or send passwords to FastAPI. The `/app` placeholder's **Verify API connection** button exercises the actual authenticated request.

## Automated checks

```powershell
cd frontend
npm.cmd run lint
npm.cmd run build
node --experimental-strip-types --test tests/workspacePolicy.test.mjs
cd ../backend
.venv/Scripts/ruff.exe check .
.venv/Scripts/pytest.exe -q
cd ..
docker compose config --quiet
```

Backend tests use ephemeral RSA keys and mocked JWKS discovery, while exercising actual JWT signature/claim verification. They do not prove that a real Clerk browser session has completed. Routing policy tests cover no membership, sole membership, multiple memberships, stale active organizations, invitations awaiting membership, and invitation continuations through sign-in, signup and password reset.

## Manual browser review

Use `http://localhost:5173`, matching the existing allowed frontend origin. The API is at `http://localhost:8001`. Other frontend origins can be intentionally rejected by CORS or the token authorized-party check.

1. Follow landing-page **Get Started**, **Build your radar**, and **Sign in** links.
2. Create a new test account with a real inbox. Confirm mismatched passwords fail locally. Verify an incorrect code fails, resend works, and the correct code establishes a session. A user with zero memberships must reach `/setup-workspace` without any organization being created.
3. Sign out, sign in with a wrong password, then with the correct password. Complete any Clerk device-trust email challenge. Check loading and error states.
4. Test **Continue with Google** using both a new and an existing account. Check callback handling and membership routing. Do not treat an HTTP 200 for the SPA shell as proof of OAuth success.
5. Run **Forgot password?**: send code, try an invalid code, resend, verify, set a new password, then confirm it works. Confirm the previous password no longer works.
6. While signed out, open `/app` and `/setup-workspace`: both must redirect to `/sign-in`. While signed in, opening `/sign-in` or `/sign-up` must route by membership.
7. Use a Clerk organization member: the organization must be activated and `/app` shown. Click **Verify API connection** to confirm a genuine Clerk session is accepted by FastAPI. Confirm sign-out returns to `/`.
8. Test multiple memberships: keep a valid active organization; without one, require a deliberate choice.
9. From Clerk, issue test invitations with an application redirect to `/accept-invitation`. Test a new user, existing signed-out user, already signed-in user, expired ticket, and an invited account requiring an extra sign-in challenge. All successful cases must join the existing brokerage and skip setup. No team UI or invitation sender is built here.
10. Inspect the browser console and network panel for unexpected errors. No password request should target FastAPI. Do not copy session tokens into reports or screenshots.

Existing Clerk email/password, email-code verification, Google, allowed redirect origins and organization settings remain authoritative. No dashboard or environment settings are changed by this implementation. Browser account flows, email delivery and acceptance of a real session require this manual review when no interactive browser connection is available.

### Clerk Organization configuration

The current Clerk Organization configuration is:

- Organization membership is optional so a newly authenticated user can reach Radory's custom `/setup-workspace` flow before an Organization exists.
- Radory requires a workspace membership before allowing access to `/app`.
- The organization membership limit is 5.
- Verified domains are disabled.
- Organization slugs are enabled.
- Automatic first organization creation is disabled.
- User-created organizations are disabled.
- The default organization roles are Admin and Member.

The application handles a pending `choose-organization` session task without introducing an individual-account mode.

Real membership and invitation transitions remain unverified: no browser connection was available, and read-only Clerk Backend API requests to list users and organizations returned HTTP 403 (without a Clerk error code). This does not establish that browser-side Clerk authentication is broken. It prevents this validation session from confirming existing membership records. No accounts, memberships, invitation records, application code, or Clerk configuration were changed during the validation rerun. Complete manual browser checks 2–9 above before treating the live flows as verified.

References: [Clerk email/password flow](https://clerk.com/docs/guides/development/custom-flows/authentication/email-password), [password reset](https://clerk.com/docs/guides/development/custom-flows/authentication/forgot-password), [organization invitations](https://clerk.com/docs/guides/development/custom-flows/organizations/accept-organization-invitations), [session token claims](https://clerk.com/docs/guides/sessions/session-tokens).
