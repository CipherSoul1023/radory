import { useAuth, useSignIn } from '@clerk/react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { AuthMessage, AuthStatus } from '../components/auth/AuthStatus'
import {
  checkClerk,
  useAuthAction,
  useAuthDestination,
  withInvitationContext,
} from '../services/auth'

export function AcceptInvitationPage() {
  const [params] = useSearchParams()
  const ticket = params.get('__clerk_ticket')
  const status = params.get('__clerk_status')
  const { isSignedIn } = useAuth({ treatPendingAsSignedOut: false })
  const { signIn } = useSignIn()
  const { busy, error, setError, run } = useAuthAction()
  const destination = useAuthDestination(true)
  const navigate = useNavigate()
  if (status === 'complete' && isSignedIn)
    return (
      <Navigate to={withInvitationContext('/auth/continue', true)} replace />
    )
  if (!ticket)
    return (
      <AuthStatus title="Invitation unavailable">
        <p className="auth-subtitle">
          Open the complete invitation link from your email.
        </p>
      </AuthStatus>
    )
  if (status === 'sign_up' && !isSignedIn)
    return <Navigate to={`/sign-up?${params.toString()}`} replace />
  return (
    <AuthStatus title="Join your brokerage">
      <p className="auth-subtitle">
        Continue with your Clerk invitation to join the existing workspace.
      </p>
      <AuthMessage error={error} />
      <button
        className="auth-primary"
        disabled={busy}
        onClick={() =>
          void run(async () => {
            await checkClerk(signIn.ticket({ ticket }))
            if (signIn.status === 'complete')
              await checkClerk(signIn.finalize({ navigate: destination }))
            else if (
              [
                'needs_second_factor',
                'needs_client_trust',
                'needs_new_password',
              ].includes(signIn.status ?? '')
            )
              navigate(withInvitationContext('/sign-in', true), {
                replace: true,
              })
            else
              setError(
                'This invitation needs additional verification. Reopen the invitation email, or contact your brokerage administrator.',
              )
          })
        }
      >
        {busy ? 'Accepting invitation…' : 'Accept invitation and continue'}
      </button>
    </AuthStatus>
  )
}
