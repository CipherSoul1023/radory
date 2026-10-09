import { useAuth } from '@clerk/react'
import { useCallback } from 'react'

export interface IdentityContext {
  user_id: string
  session_id: string
  organization_id: string | null
  organization_role: string | null
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
  }
}

function errorMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object' || !('detail' in payload)) return null
  const detail = payload.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) =>
        item && typeof item === 'object' && 'msg' in item
          ? String(item.msg)
          : null,
      )
      .filter(Boolean)
      .join(' ')
  }
  return null
}

export function useAuthenticatedRequest() {
  const { getToken } = useAuth()
  return useCallback(async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const token = await getToken()
    if (!token) throw new ApiError('Your session is not ready. Please sign in again.', 401)
    const base = import.meta.env.VITE_API_URL || 'http://localhost:8001'
    const response = await fetch(`${base.replace(/\/$/, '')}${path}`, {
      ...init,
      headers: {
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
        Authorization: `Bearer ${token}`,
      },
      cache: 'no-store',
    })
    if (response.status === 401)
      throw new ApiError('Your session could not be verified. Please sign in again.', 401)
    if (!response.ok) {
      let payload: unknown
      try {
        payload = await response.json()
      } catch {
        payload = null
      }
      throw new ApiError(
        errorMessage(payload) || 'The API is unavailable. Please try again.',
        response.status,
      )
    }
    return response.json() as Promise<T>
  }, [getToken])
}

export function useAuthenticatedApi() {
  const request = useAuthenticatedRequest()
  return async (): Promise<IdentityContext> => {
    return request<IdentityContext>('/api/me')
  }
}
