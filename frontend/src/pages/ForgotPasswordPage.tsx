import { useSignIn } from '@clerk/react'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { EmailField, PasswordField } from '../components/auth/AuthControls'
import {
  AuthMessage,
  AuthStatus,
  CodeField,
} from '../components/auth/AuthStatus'
import {
  checkClerk,
  field,
  hasInvitationContext,
  useAuthAction,
  useAuthDestination,
  withInvitationContext,
} from '../services/auth'

export function ForgotPasswordPage() {
  const { signIn, fetchStatus } = useSignIn()
  const [sent, setSent] = useState(false)
  const [message, setMessage] = useState('')
  const { busy, error, setError, run } = useAuthAction()
  const [params] = useSearchParams()
  const invited = hasInvitationContext(params)
  const destination = useAuthDestination(invited)
  const navigate = useNavigate()
  const newPassword = signIn.status === 'needs_new_password'
  const disabled = busy || fetchStatus === 'fetching'
  return (
    <AuthStatus
      title={
        newPassword
          ? 'Choose a new password'
          : sent
            ? 'Check your email'
            : 'Reset your password'
      }
    >
      <p className="auth-subtitle">
        {sent
          ? 'Enter the code sent to your work email.'
          : 'We’ll email you a code to reset your password securely.'}
      </p>
      <AuthMessage error={error} message={message} />
      <form
        onSubmit={(event) => {
          event.preventDefault()
          const form = event.currentTarget
          if (
            newPassword &&
            field(form, 'reset-password') !== field(form, 'reset-confirm')
          ) {
            setError('Your passwords do not match.')
            return
          }
          void run(async () => {
            if (newPassword) {
              await checkClerk(
                signIn.resetPasswordEmailCode.submitPassword({
                  password: field(form, 'reset-password'),
                  signOutOfOtherSessions: true,
                }),
              )
              if ((signIn.status as string) === 'complete')
                await checkClerk(signIn.finalize({ navigate: destination }))
              else
                navigate(withInvitationContext('/sign-in', invited), {
                  replace: true,
                })
            } else if (sent)
              await checkClerk(
                signIn.resetPasswordEmailCode.verifyCode({
                  code: field(form, 'code').trim(),
                }),
              )
            else {
              await checkClerk(
                signIn.create({
                  identifier: field(form, 'reset-email').trim(),
                }),
              )
              await checkClerk(signIn.resetPasswordEmailCode.sendCode())
              setSent(true)
            }
          })
        }}
      >
        <fieldset disabled={disabled}>
          {newPassword ? (
            <>
              <PasswordField
                id="reset-password"
                label="New password"
                placeholder="Create a strong password"
                autoComplete="new-password"
              />
              <PasswordField
                id="reset-confirm"
                label="Confirm password"
                placeholder="Confirm your password"
                autoComplete="new-password"
              />
            </>
          ) : sent ? (
            <CodeField />
          ) : (
            <EmailField
              id="reset-email"
              label="Work email"
              placeholder="you@yourbrokerage.com"
              autoComplete="email"
            />
          )}
          <button className="auth-primary" type="submit">
            {disabled
              ? 'Please wait…'
              : newPassword
                ? 'Save password'
                : sent
                  ? 'Verify code'
                  : 'Send reset code'}
          </button>
        </fieldset>
      </form>
      {sent && !newPassword && (
        <button
          className="auth-text-button"
          disabled={disabled}
          onClick={() =>
            void run(async () => {
              await checkClerk(signIn.resetPasswordEmailCode.sendCode())
              setMessage('A new reset code has been sent.')
            })
          }
        >
          Resend reset code
        </button>
      )}
      <div className="auth-switch">
        <Link to={withInvitationContext('/sign-in', invited)}>
          Back to sign in
        </Link>
      </div>
    </AuthStatus>
  )
}
