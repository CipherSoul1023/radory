import { HandleSSOCallback, useAuth, useClerk, useSession } from '@clerk/react'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
  useSearchParams,
} from 'react-router-dom'
import { useAuthenticatedApi } from '../../services/api'
import {
  hasInvitationContext,
  useAuthAction,
  useAuthDestination,
  withInvitationContext,
} from '../../services/auth'
import {
  workspaceDecision,
  type Membership,
} from '../../services/workspacePolicy'
import { withActiveSignUpAttempt } from '../../services/signupState'
import { AuthMessage, AuthStatus } from './AuthStatus'

export function AuthReady({ children }: { children: ReactNode }) {
  if (!import.meta.env.VITE_CLERK_PUBLISHABLE_KEY)
    return (
      <AuthStatus title="Sign-in unavailable">
        <p className="auth-subtitle">
          Authentication is not configured for this environment.
        </p>
        <Link to="/">Return home</Link>
      </AuthStatus>
    )
  return <ClerkReady>{children}</ClerkReady>
}

function ClerkReady({ children }: { children: ReactNode }) {
  const { isLoaded } = useAuth({ treatPendingAsSignedOut: false })
  if (!isLoaded) return <AuthStatus title="Loading secure sign-in…" />
  return children
}

export function AuthEntry({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth({ treatPendingAsSignedOut: false })
  const [params] = useSearchParams()
  const invited = hasInvitationContext(params)
  if (!isLoaded) return <AuthStatus title="Loading your session…" />
  if (isSignedIn)
    return (
      <Navigate
        to={withInvitationContext('/auth/continue', invited)}
        replace
      />
    )
  return children
}

export function SsoCallbackPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const invited = hasInvitationContext(params)
  const destination = useAuthDestination(invited)
  return (
    <AuthStatus title="Completing sign-in…">
      <HandleSSOCallback
        navigateToApp={destination}
        navigateToSignIn={() =>
          navigate(withInvitationContext('/sign-in', invited), {
            replace: true,
          })
        }
        navigateToSignUp={() =>
          navigate(
            withActiveSignUpAttempt(
              withInvitationContext('/sign-up', invited),
            ),
            { replace: true },
          )
        }
      />
    </AuthStatus>
  )
}

function SignOutButton() {
  const { signOut } = useClerk()
  const { busy, error, run } = useAuthAction()
  return (
    <>
      <button
        className="auth-text-button"
        disabled={busy}
        onClick={() =>
          void run(async () => {
            await signOut({ redirectUrl: '/' })
          })
        }
      >
        {busy ? 'Signing out…' : 'Sign out'}
      </button>
      <AuthMessage error={error} />
    </>
  )
}

export function WorkspaceGate() {
  const { isLoaded, isSignedIn, orgId } = useAuth({
    treatPendingAsSignedOut: false,
  })
  const { session } = useSession()
  const clerk = useClerk()
  const location = useLocation()
  const [params] = useSearchParams()
  const invited = hasInvitationContext(params)
  const { busy, error, run } = useAuthAction()
  const memberships = useQuery({
    queryKey: ['workspace-memberships', session?.id, orgId, location.key],
    enabled: Boolean(isLoaded && isSignedIn && session?.user),
    retry: 1,
    queryFn: async () => {
      const user = session!.user!
      const result: Membership[] = []
      // Fetch every page; never mistake a partial list for a single membership.
      for (let initialPage = 1; ; initialPage += 1) {
        const page = await user.getOrganizationMemberships({
          pageSize: 100,
          initialPage,
        })
        result.push(...page.data)
        if (result.length >= page.total_count) return result
        if (!page.data.length) throw new Error('Incomplete membership response')
      }
    },
  })
  if (!isLoaded) return <AuthStatus title="Loading your session…" />
  if (!isSignedIn)
    return (
      <Navigate to={withInvitationContext('/sign-in', invited)} replace />
    )
  if (memberships.isPending || memberships.isFetching)
    return <AuthStatus title="Loading your brokerage…" />
  if (memberships.isError)
    return (
      <AuthStatus title="Unable to load your brokerage">
        <p className="auth-subtitle">
          Please retry so we can confirm your workspace membership.
        </p>
        <button
          className="auth-primary"
          onClick={() => void memberships.refetch()}
        >
          Try again
        </button>
        <SignOutButton />
      </AuthStatus>
    )
  const decision = workspaceDecision(memberships.data, orgId, invited)
  const task = session?.currentTask?.key
  if (task && task !== 'choose-organization')
    return (
      <AuthStatus title="Your account needs attention">
        <p className="auth-subtitle">
          {task === 'reset-password'
            ? 'Reset your password to continue.'
            : 'Your organization requires multi-factor authentication setup. Please contact your administrator to complete this account requirement.'}
        </p>
        {task === 'reset-password' && (
          <Link
            className="auth-text-button"
            to={withInvitationContext('/forgot-password', invited)}
          >
            Reset password
          </Link>
        )}
        <SignOutButton />
      </AuthStatus>
    )
  if (decision.kind === 'activate')
    return <ActivateWorkspace organizationId={decision.organizationId} />
  if (decision.kind === 'choose')
    return (
      <AuthStatus title="Choose your brokerage">
        <p className="auth-subtitle">Select the workspace you want to open.</p>
        <AuthMessage error={error} />
        <div className="auth-workspaces">
          {memberships.data.map(({ organization }) => (
            <button
              className="auth-primary"
              key={organization.id}
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  await clerk.setActive({ organization: organization.id })
                })
              }
            >
              {organization.name}
            </button>
          ))}
        </div>
        <SignOutButton />
      </AuthStatus>
    )
  if (decision.kind === 'invitation-pending')
    return (
      <AuthStatus title="Confirming your invitation">
        <p className="auth-subtitle">
          Your brokerage membership is not available yet. Retry, or reopen the
          invitation from your email.
        </p>
        <button
          className="auth-primary"
          onClick={() => void memberships.refetch()}
        >
          Check membership again
        </button>
        <SignOutButton />
      </AuthStatus>
    )
  if (decision.kind === 'setup') {
    if (location.pathname !== '/setup-workspace')
      return <Navigate to="/setup-workspace" replace />
    return (
      <AuthStatus title="Let’s set up your brokerage">
        <p className="auth-subtitle">
          Your account is ready. Next, you’ll set up a brokerage workspace for
          yourself and your team.
        </p>
        <SignOutButton />
      </AuthStatus>
    )
  }
  // Membership alone is insufficient: activation and all Clerk session tasks must finish.
  if (session?.status !== 'active')
    return (
      <AuthStatus title="Completing your session…">
        <button
          className="auth-primary"
          onClick={() =>
            void run(async () => {
              await clerk.setActive({ organization: decision.organizationId })
              await session?.reload()
            })
          }
        >
          Continue to workspace
        </button>
        <AuthMessage error={error} />
        <SignOutButton />
      </AuthStatus>
    )
  if (location.pathname !== '/app') return <Navigate to="/app" replace />
  return (
    <AppPlaceholder
      name={
        memberships.data.find(
          ({ organization }) => organization.id === decision.organizationId,
        )!.organization.name
      }
    />
  )
}

function ActivateWorkspace({ organizationId }: { organizationId: string }) {
  const clerk = useClerk()
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let cancelled = false
    void clerk.setActive({ organization: organizationId }).catch(() => {
      if (!cancelled) setFailed(true)
    })
    return () => {
      cancelled = true
    }
  }, [clerk, organizationId])
  return (
    <AuthStatus
      title={
        failed ? 'Unable to open your brokerage' : 'Opening your brokerage…'
      }
    >
      {failed && (
        <button
          className="auth-primary"
          onClick={() => window.location.reload()}
        >
          Try again
        </button>
      )}
      <SignOutButton />
    </AuthStatus>
  )
}

function AppPlaceholder({ name }: { name: string }) {
  const requestIdentity = useAuthenticatedApi()
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  return (
    <AuthStatus title={name}>
      <p className="auth-subtitle">
        You’re signed in to your brokerage workspace.
      </p>
      <button
        className="auth-primary"
        disabled={busy}
        onClick={async () => {
          setBusy(true)
          setMessage('')
          try {
            await requestIdentity()
            setMessage('Your session was verified by Radory’s API.')
          } catch (error) {
            setMessage(
              error instanceof Error
                ? error.message
                : 'Unable to reach the API.',
            )
          } finally {
            setBusy(false)
          }
        }}
      >
        {busy ? 'Checking session…' : 'Verify API connection'}
      </button>
      <p className="auth-note" role="status">
        {message}
      </p>
      <SignOutButton />
    </AuthStatus>
  )
}
