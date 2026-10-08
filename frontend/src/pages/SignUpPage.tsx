import { useAuth, useSignUp } from '@clerk/react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { AuthMessage, CodeField } from '../components/auth/AuthStatus'
import {
  checkClerk,
  field,
  hasInvitationContext,
  useAuthAction,
  useAuthDestination,
  withInvitationContext,
} from '../services/auth'
import { AuthLayout } from '../components/auth/AuthLayout'
import {
  EmailField,
  GoogleButton,
  PasswordField,
} from '../components/auth/AuthControls'

const signUpVisual = {
  tag: 'Intelligence → Opportunity',
  title: 'Know who’s about to',
  accent: 'need space.',
  description:
    'Spot companies approaching real estate decisions before their requirements become obvious to the market.',
  bullets: ['Company signals', 'Tenant demand', 'Opportunity timing'],
} as const

export function SignUpPage() {
  const { isSignedIn } = useAuth({ treatPendingAsSignedOut: false })
  const { signUp, fetchStatus } = useSignUp()
  const [params] = useSearchParams()
  const ticket = params.get('__clerk_ticket')
  const invited = hasInvitationContext(params)
  const { busy, error, setError, run } = useAuthAction()
  const [message, setMessage] = useState('')
  const [verify, setVerify] = useState(
    signUp.unverifiedFields.includes('email_address'),
  )
  const destination = useAuthDestination(invited)
  const disabled = busy || fetchStatus === 'fetching'

  async function finishOrVerify() {
    if (signUp.status === 'complete') {
      await checkClerk(signUp.finalize({ navigate: destination }))
    } else if (signUp.unverifiedFields.includes('email_address')) {
      setVerify(true)
      await checkClerk(signUp.verifications.sendEmailCode())
      setMessage('Check your inbox for your verification code.')
    } else {
      setError(
        'Your account needs additional information required by Clerk. Please contact your administrator to review the sign-up requirements.',
      )
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const password = field(form, 'signup-password')
    if (password !== field(form, 'signup-confirm')) {
      setError('Your passwords do not match.')
      return
    }
    void run(async () => {
      if (ticket)
        await checkClerk(
          signUp.create({ strategy: 'ticket', ticket, password }),
        )
      else
        await checkClerk(
          signUp.password({
            emailAddress: field(form, 'signup-email').trim(),
            password,
          }),
        )
      await finishOrVerify()
    })
  }

  function verifyCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const code = field(event.currentTarget, 'code').trim()
    void run(async () => {
      await checkClerk(signUp.verifications.verifyEmailCode({ code }))
      if (signUp.status === 'complete')
        await checkClerk(signUp.finalize({ navigate: destination }))
      else
        setError(
          'Verification is complete, but your account still has additional requirements. Please contact your administrator.',
        )
    })
  }

  if (isSignedIn)
    return (
      <Navigate
        replace
        to={
          ticket && signUp.status !== 'complete'
            ? `/accept-invitation?${params.toString()}`
            : withInvitationContext('/auth/continue', invited)
        }
      />
    )

  if (verify)
    return (
      <AuthLayout visual={signUpVisual}>
        <div className="auth-card">
          <div className="auth-eyebrow">One more step</div>
          <h1>Verify your email</h1>
          <p className="auth-subtitle">
            Enter the code sent to your work email to finish creating your
            account.
          </p>
          <AuthMessage error={error} message={message} />
          <form onSubmit={verifyCode}>
            <fieldset disabled={disabled}>
              <CodeField />
              <button className="auth-primary" type="submit">
                {disabled ? 'Verifying…' : 'Verify email'}
              </button>
            </fieldset>
          </form>
          <button
            className="auth-text-button"
            disabled={disabled}
            onClick={() =>
              void run(async () => {
                await checkClerk(signUp.verifications.sendEmailCode())
                setMessage('A new verification code has been sent.')
              })
            }
          >
            Resend verification code
          </button>
          <div id="clerk-captcha" />
        </div>
      </AuthLayout>
    )

  return (
    <AuthLayout visual={signUpVisual}>
      <div className="auth-card">
        <div className="auth-eyebrow">Start building your radar</div>
        <h1>Create your account</h1>
        <p className="auth-subtitle">
          Create your Radory account. Your brokerage workspace and market
          profile come next.
        </p>

        <AuthMessage error={error} />
        {ticket && (
          <p className="auth-note">
            Your invitation verifies your email and joins the existing
            brokerage. Create a password to continue.
          </p>
        )}
        <GoogleButton
          disabled={disabled || Boolean(ticket)}
          onClick={() =>
            void run(async () => {
              await checkClerk(
                signUp.sso({
                  strategy: 'oauth_google',
                  redirectCallbackUrl: withInvitationContext(
                    '/sso-callback',
                    invited,
                  ),
                  redirectUrl: withInvitationContext(
                    '/auth/continue',
                    invited,
                  ),
                }),
              )
            })
          }
        />
        <div className="auth-divider">or continue with email</div>

        <form onSubmit={submit}>
          <fieldset disabled={disabled}>
            <EmailField
              id="signup-email"
              label="Work email"
              placeholder="you@yourbrokerage.com"
              autoComplete="email"
              required={!ticket}
            />
            <PasswordField
              id="signup-password"
              label="Password"
              placeholder="Create a strong password"
              autoComplete="new-password"
            />
            <PasswordField
              id="signup-confirm"
              label="Confirm password"
              placeholder="Confirm your password"
              autoComplete="new-password"
            />
            <button className="auth-primary" type="submit">
              {disabled ? 'Creating account…' : 'Create account →'}
            </button>
            <div className="auth-note">
              We’ll verify your email before you set up your brokerage
              workspace.
            </div>
          </fieldset>
        </form>
        <div id="clerk-captcha" />

        <div className="auth-switch">
          Already have an account?{' '}
          <Link
            to={
              ticket
                ? `/accept-invitation?${new URLSearchParams({ __clerk_ticket: ticket, __clerk_status: 'sign_in' }).toString()}`
                : withInvitationContext('/sign-in', invited)
            }
          >
            Sign in
          </Link>
        </div>
        <div className="auth-secure">
          🔒 Secure authentication powered by Clerk
        </div>
      </div>
    </AuthLayout>
  )
}
