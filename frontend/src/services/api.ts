import { useAuth } from '@clerk/react'

export interface IdentityContext {
  user_id: string
  session_id: string
  organization_id: string | null
  organization_role: string | null
}

export function useAuthenticatedApi() {
  const { getToken } = useAuth()
  return async (): Promise<IdentityContext> => {
    const token = await getToken()
    if (!token)
      throw new Error('Your session is not ready. Please sign in again.')
    const base = import.meta.env.VITE_API_URL || 'http://localhost:8001'
    const response = await fetch(`${base.replace(/\/$/, '')}/api/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    })
    if (response.status === 401)
      throw new Error(
        'Your session could not be verified. Please sign in again.',
      )
    if (!response.ok)
      throw new Error('The API is unavailable. Please try again.')
    return response.json()
  }
}
