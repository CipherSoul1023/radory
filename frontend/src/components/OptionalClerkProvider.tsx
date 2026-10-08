import { ClerkProvider } from '@clerk/react'
import type { ReactNode } from 'react'

export function OptionalClerkProvider({ children }: { children: ReactNode }) {
  const clerkKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY
  if (!clerkKey) return children

  return (
    <ClerkProvider
      publishableKey={clerkKey}
      signInUrl="/sign-in"
      signUpUrl="/sign-up"
      signInFallbackRedirectUrl="/auth/continue"
      signUpFallbackRedirectUrl="/auth/continue"
      taskUrls={{
        'choose-organization': '/auth/continue',
        'reset-password': '/auth/continue',
        'setup-mfa': '/auth/continue',
      }}
    >
      {children}
    </ClerkProvider>
  )
}
