import { useSignIn } from '@clerk/react'
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
import { withNewSignUpIntent } from '../services/signupState'
import {
  EmailField,
  GoogleButton,
  PasswordField,
} from '../components/auth/AuthControls'

const signInVisual = {
  tag: 'Your market. Your radar.',
  title: 'Step back into',
  accent: 'your radar.',
  description:
    'Monitor company movement, track demand signals and stay ahead of the next commercial real estate requirement.',
  bullets: ['Monitor targets', 'Track signals', 'Act earlier'],
} as const

export function SignInPage() {
  const { signIn, fetchStatus } = useSignIn()
  const { busy, error, setError, run } = useAuthAction()
  const [factor, setFactor] = useState<
    'email_code' | 'totp' | 'phone_code' | null
  >(null)
  const [params] = useSearchParams()
  const invited = hasInvitationContext(params)
  const destination = useAuthDestination(invited)
  const disabled = busy || fetchStatus === 'fetching'
  const needsVerification =
    signIn.status === 'needs_client_trust' ||
    signIn.status === 'needs_second_factor'

  async function finish() {
    if (signIn.status === 'complete')
      await checkClerk(signIn.finalize({ navigate: destination }))
    else if (
      signIn.status !== 'needs_client_trust' &&
      signIn.status !== 'needs_second_factor'
    )
      setError(
        'Sign-in needs another step. Please try again or reset your password.',
      )
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    void run(async () => {
      await checkClerk(
        signIn.password({
          emailAddress: field(form, 'signin-email').trim(),
          password: field(form, 'signin-password'),
        }),
      )
      await finish()
    })
  }

  if (needsVerification)
    return (
      <AuthLayout visual={signInVisual}>
        <div className="auth-card">
          <h1>Verify your sign-in</h1>
          <p className="auth-subtitle">
            Complete the extra verification to securely access your brokerage.
          </p>
          <AuthMessage error={error} />
          {!factor ? (
            <div className="auth-workspaces">
              {signIn.supportedSecondFactors
                .filter((item) =>
                  ['email_code', 'phone_code', 'totp'].includes(item.strategy),
                )
                .map((item) => (
                  <button
                    className="auth-primary"
                    disabled={disabled}
                    key={item.strategy}
                    onClick={() =>
                      void run(async () => {
                        if (item.strategy === 'email_code') {
                          await checkClerk(signIn.mfa.sendEmailCode())
                          setFactor('email_code')
                        }
                        if (item.strategy === 'phone_code') {
                          await checkClerk(signIn.mfa.sendPhoneCode())
                          setFactor('phone_code')
                        }
                        if (item.strategy === 'totp') setFactor('totp')
                      })
                    }
                  >
                    {item.strategy === 'totp'
                      ? 'Use authenticator app'
                      : item.strategy === 'email_code'
                        ? 'Send email code'
                        : 'Send text message code'}
                  </button>
                ))}
            </div>
          ) : (
            <form
              onSubmit={(event) => {
                event.preventDefault()
                const code = field(event.currentTarget, 'code').trim()
                void run(async () => {
                  await checkClerk(
                    factor === 'totp'
                      ? signIn.mfa.verifyTOTP({ code })
                      : factor === 'email_code'
                        ? signIn.mfa.verifyEmailCode({ code })
                        : signIn.mfa.verifyPhoneCode({ code }),
                  )
                  await finish()
                })
              }}
            >
              <fieldset disabled={disabled}>
                <CodeField />
                <button className="auth-primary" type="submit">
                  {disabled ? 'Verifying…' : 'Verify and sign in'}
                </button>
              </fieldset>
            </form>
          )}
          <Link
            className="auth-text-button"
            to={withInvitationContext('/forgot-password', invited)}
          >
            Reset password
          </Link>
        </div>
      </AuthLayout>
    )

  if (signIn.status === 'needs_new_password')
    return (
      <Navigate
        to={withInvitationContext('/forgot-password', invited)}
        replace
      />
    )

  return (
    <AuthLayout visual={signInVisual}>
      <div className="auth-card">
        <div className="auth-eyebrow">Welcome back</div>
        <h1>Sign in to Radory</h1>
        <p className="auth-subtitle">
          Return to your workspace and continue tracking the companies and
          markets that matter to your brokerage.
        </p>

        <AuthMessage error={error} />
        <GoogleButton
          disabled={disabled}
          onClick={() =>
            void run(async () => {
              await checkClerk(
                signIn.sso({
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
              id="signin-email"
              label="Work email"
              placeholder="you@yourbrokerage.com"
              autoComplete="email"
            />
            <PasswordField
              id="signin-password"
              label="Password"
              placeholder="Enter your password"
              autoComplete="current-password"
            />
            <div className="auth-help-row">
              <Link to={withInvitationContext('/forgot-password', invited)}>
                Forgot password?
              </Link>
            </div>
            <button className="auth-primary" type="submit">
              {disabled ? 'Signing in…' : 'Sign in →'}
            </button>
          </fieldset>
        </form>
        <div id="clerk-captcha" />

        <div className="auth-switch">
          New to Radory?{' '}
          <Link
            to={
              invited
                ? withInvitationContext('/sign-up', true)
                : withNewSignUpIntent('/sign-up')
            }
          >
            Create an account
          </Link>
        </div>
        <div className="auth-secure">
          🔒 Secure authentication powered by Clerk
        </div>
      </div>
    </AuthLayout>
  )
}
