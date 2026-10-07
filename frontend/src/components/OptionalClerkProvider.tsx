import { Suspense, lazy, type ReactNode } from 'react'

const ClerkProvider = lazy(async () => {
  const { ClerkProvider } = await import('@clerk/react')
  return { default: ClerkProvider }
})

export function OptionalClerkProvider({ children }: { children: ReactNode }) {
  const clerkKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY
  if (!clerkKey) return children

  return (
    <Suspense fallback={null}>
      <ClerkProvider publishableKey={clerkKey}>{children}</ClerkProvider>
    </Suspense>
  )
}
