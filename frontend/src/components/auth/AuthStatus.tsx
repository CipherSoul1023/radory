import type { ReactNode } from 'react'
import { AuthLayout } from './AuthLayout'

export function AuthStatus({
  title,
  children,
}: {
  title: string
  children?: ReactNode
}) {
  return (
    <AuthLayout
      visual={{
        tag: 'Your market. Your radar.',
        title: 'Step back into',
        accent: 'your radar.',
        description:
          'A workspace for your brokerage and the opportunities ahead.',
        bullets: ['Monitor targets', 'Track signals', 'Act earlier'],
      }}
    >
      <div className="auth-card">
        <h1>{title}</h1>
        {children}
      </div>
    </AuthLayout>
  )
}

export function AuthMessage({
  error,
  message,
}: {
  error?: string
  message?: string
}) {
  return (
    <>
      {error && (
        <p className="auth-error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="auth-note" role="status">
          {message}
        </p>
      )}
    </>
  )
}

export function CodeField() {
  return (
    <div className="auth-field">
      <label htmlFor="verification-code">Verification code</label>
      <div className="auth-input-wrap">
        <input
          id="verification-code"
          name="code"
          autoComplete="one-time-code"
          inputMode="numeric"
          required
          placeholder="Enter your code"
        />
      </div>
    </div>
  )
}
